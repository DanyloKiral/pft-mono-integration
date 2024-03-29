import logging
import time

from datetime import datetime
from firefly_flow.mapper import Mapper
from utils import add_days, save_to_json_file, now
from mono_api import MonoApi
from firefly_api import FireflyApi
from utils.files import remove_file_if_exists, save_list_to_csv_file

class ImportFlow:
    def __init__(self, configs, credentials):
        self.configs = configs
        self.api_credentials = credentials

        self.mono_api = MonoApi(configs["mono"], credentials["mono"])
        self.firefly_api = FireflyApi(configs["firefly"], credentials["firefly"])
        logging.info("initiated apis")

    def run_import(self):
        requests_interval_sec = self.configs["mono"]["options"]["requests_interval_sec"]
        accounts_mapping = self.create_account_mappings()
        logging.info("created account mappings")

        all_transactions = []
        number_of_iterations_left = len(accounts_mapping)
        for account in accounts_mapping:
            new_transactions = []
            number_of_iterations_left -= 1
            firefly_acc = account["firefly_acc"]
            mono_acc = account["mono_acc"]
            logging.info(f"loading transactions for account {firefly_acc['name']}")

            latest_transactions = self.firefly_api.get_latest_transactions(firefly_acc["id"])
            transactions_per_date = self.__group_transaction_per_date(latest_transactions)

            import_from_date, same_day_ids = self.__get_import_params(transactions_per_date)
            new_account_transactions = self.mono_api.get_statement(
                mono_acc["id"],
                from_date=import_from_date
            )
            new_account_transactions = self.__filter_transactions(latest_transactions, new_account_transactions)

            account["new_account_transactions"] = new_account_transactions
            new_account_transactions = Mapper.map_to_firefly_transactions(
                new_account_transactions, firefly_acc, self.configs["mono"]["options"]["add_mcc_tag"])
            if len(new_account_transactions) > 0:
                all_transactions = all_transactions + new_account_transactions
                self.firefly_api.insert_transactions(new_account_transactions)
                logging.info(f"loaded {len(new_account_transactions)} new transactions for account {firefly_acc['name']}")
            else:
                logging.info(f"no new transactions for account {firefly_acc['name']} found")

            if number_of_iterations_left > 0:
                time.sleep(requests_interval_sec)
        if len(all_transactions) < 1:
            logging.info("no new transactions available.fin")
            return
        logging.info(f"checked all accounts for new transactions. \nInserted {len(all_transactions)} transactions")
        self.__write_data_log(all_transactions)

    def create_account_mappings(self):
        client_info = self.mono_api.get_client_info()
        firefly_accounts = self.firefly_api.get_accounts()
        accounts_mapping = Mapper.create_accounts_mapping(
            self.configs["mappings"]["accounts"],
            client_info,
            firefly_accounts
        )
        return accounts_mapping

    def __write_data_log(self, all_transactions):
        current_timestamp = datetime.now().strftime('%Y-%m-%dT%H:%M')
        data_log_folder = self.configs.get("logs").get("data_log_folder")
        data_log_filename = f"{data_log_folder}/new_transactions_{current_timestamp}.json"
        save_to_json_file(all_transactions, data_log_filename)
        logging.info(f"saved data log to {data_log_filename}.")
    
    @staticmethod
    def __filter_transactions(firefly_acc_transactions, new_mono_transactions):
        external_ids = set([tr["external_id"] for tr in firefly_acc_transactions
                            if tr["external_id"] is not None and len(tr["external_id"]) > 0])

        return [tr for tr in new_mono_transactions
                if tr["id"] not in external_ids]
    
    @staticmethod
    def __group_transaction_per_date(latest_transactions: list):
        transactions_per_date = {}
        for trans in latest_transactions:
            date_trans_list = transactions_per_date.setdefault(trans["date"], [])
            transaction_external_id = trans["external_id"]
            if transaction_external_id is not None:
                date_trans_list.append(transaction_external_id)
        return transactions_per_date
    
    def __get_import_params(self, transactions_per_date: dict):
        min_import_start_date = add_days(now(), -1 * self.configs["mono"]["options"]["max_statement_days"]).date()
        if len(transactions_per_date.keys()) == 0:
            default_start_date = datetime.strptime(
                self.configs["mono"]["options"]["default_start_date"],
                "%Y-%m-%d").date()
            start_date = default_start_date if (default_start_date > min_import_start_date) else min_import_start_date
            logging.info(f"No items in transactions_per_date - starting from {start_date}")

            return start_date, []
        last_transaction_date = max(transactions_per_date.keys())
        same_day_ids = transactions_per_date.get(last_transaction_date)
        start_date = datetime.fromisoformat(last_transaction_date).date()
        if len(same_day_ids) == 0:
            start_date = add_days(start_date, 1)
        start_date = start_date if (start_date > min_import_start_date) else min_import_start_date
        logging.info(f"Starting from {start_date}")

        return start_date, same_day_ids