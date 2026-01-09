# Copyright © 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# END COPYRIGHT

import logging
import os

import requests

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10


class AbsenceManager:
    """
    Absence Manager for company's intranet.

    Refer to the following link for the full API
    https://docs.oracle.com/en/cloud/saas/human-resources/25b/farws/index.html
    """

    def __init__(self, client_id, client_secret, associate_id):
        """
        Constructs an Absence Manager for company's intranet.
        @param client_id: The API client ID.
        @param client_secret: The API client secret.
        @param associate_id: an associate ID.
        """
        self.base_url = os.environ.get("MI_BASE_URL", None)
        logger.debug("BASE_URL: %s", self.base_url)

        self.app_url = os.environ.get("MI_APP_URL", None)
        logger.debug("APP_URL: %s", self.app_url)

        # Get the client_id, client_secret, and associate_id from the environment variables
        if client_id is None:
            logger.debug("AbsenceManager: no client_id provided, checking environment variables")
            client_id = os.getenv("ABSENCE_MANAGER_CLIENT_ID", None)
            if client_id is None:
                logger.debug("AbsenceManager: ABSENCE_MANAGER_CLIENT_ID is NOT defined")
            else:
                logger.debug("AbsenceManager: client_id found in environment variables")
        if client_secret is None:
            logger.debug("AbsenceManager: no client_secret provided, checking environment variables")
            client_secret = os.getenv("ABSENCE_MANAGER_CLIENT_SECRET", None)
            if client_secret is None:
                logger.debug("AbsenceManager: ABSENCE_MANAGER_CLIENT_SECRET is NOT defined")
            else:
                logger.debug("AbsenceManager: client_secret found in environment variables")
        if associate_id is None:
            logger.debug("AbsenceManager: no associate_id provided, checking environment variables")
            associate_id = os.getenv("ASSOCIATE_ID", None)
            if associate_id is None:
                logger.debug("AbsenceManager: ASSOCIATE_ID is NOT defined")
            else:
                logger.debug("AbsenceManager: associate_id found in environment variables")

        if client_id is None or client_secret is None or associate_id is None:
            logger.error(
                "ERROR: AbsenceManager is NOT configured. Please check your parameters or environment variables."
            )
            # The service is not configured. We cannot query the API, but we can still use a mock response.
            self.is_configured = False
        else:
            # The service is configured. We can query the API.
            self.is_configured = True
            # Keep track of the params
            self.client_id = client_id
            self.client_secret = client_secret
            self.associate_id = associate_id
            # Get an access token
            access_token = self.get_access_token()
            # Set the headers
            self.headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "SourceType": "Web",
            }

    def get_access_token(self):
        """
        Get the access token.
        URL: /hcm/token
        @return: and access token
        """
        token_url = f"{self.base_url}/hcm/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded", "AssociateID": self.associate_id}
        data = {"client_id": self.client_id, "client_secret": self.client_secret, "grant_type": "client_credentials"}
        response = requests.post(token_url, headers=headers, data=data, timeout=TIMEOUT_SECONDS)
        access_token = response.json()["access_token"]
        return access_token

    def get_absence_types(self, start_date):
        """
        Get absence types.
        URL: /hcm/leave/details
        :param start_date: The start date for the absence types (format: 'YYYY-MM-DD').
        :return: JSON response from the API.
        """
        url = f"{self.base_url}/hcm/leave/details"
        payload = {"Start_date": start_date}
        response = requests.post(url, headers=self.headers, json=payload, timeout=TIMEOUT_SECONDS)
        return response.json()

    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-positional-arguments
    def get_absence_details(self, start_date, end_date, abs_pin, partial_days, absence_reason):  # /hcm/leave/selection
        """
        Get absence details.

        :param start_date: Start date (format: 'YYYY-MM-DD').
        :param end_date: End date (format: 'YYYY-MM-DD').
        :param abs_pin: Absence PIN.
        :param partial_days: Partial days.
        :param absence_reason: Absence reason.
        :return: JSON response from the API.
        """
        url = f"{self.base_url}/hcm/leave/selection"
        payload = {
            "Start_date": start_date,
            "End_date": end_date,
            "Abs_pin": abs_pin,
            "Partial_days": partial_days,
            "Absence_Reason": absence_reason,
        }
        response = requests.post(url, headers=self.headers, json=payload, timeout=TIMEOUT_SECONDS)
        return response.json()

    # pylint: disable=too-many-locals
    def post_absence_details(
        self,
        begin_dt,
        end_dt,
        abs_pin,
        duration,
        current_bal,
        leave_descr,
        absence_reason,
        partial_days,
        partial_hours,
        partial_hrs1,
        partial_hrs2,
        comments,
        add_attachment,
        file_name,
        file_extn,
        file_input,
    ):  # /hcm/leave/submission
        """
        Post absence details.

        :param begin_dt: Begin date (format: 'YYYY-MM-DD').
        :param end_dt: End date (format: 'YYYY-MM-DD').
        :param abs_pin: Absence PIN.
        :param duration: Duration.
        :param current_bal: Current balance.
        :param leave_descr: Leave description.
        :param absence_reason: Absence reason.
        :param partial_days: Partial days.
        :param partial_hrs1: Partial hours 1.
        :param partial_hrs2: Partial hours 2.
        :param comments: Comments.
        :param add_attachment: Add attachment (0 or 1).
        :param file_name: File name (if attachment is added).
        :param file_extn: File extension (if attachment is added).
        :param file_input: File input (file content in base64, if attachment is added).
        :return: JSON response from the API.
        """
        url = f"{self.base_url}/hcm/leave/submission"
        payload = {
            "Begin_dt": begin_dt,
            "End_dt": end_dt,
            "Abspin": abs_pin,
            "Duration": duration,
            "Current_bal": current_bal,
            "LeaveDescr": leave_descr,
            "Absence_Reason": absence_reason,
            "Partial_Days": partial_days,
            "Partial_Hours": partial_hours,
            "Partial_Hrs1": partial_hrs1,
            "Partial_Hrs2": partial_hrs2,
            "Comments": comments,
            "Addattachment": add_attachment,
            "FileName": file_name,
            "FileExtn": file_extn,
            "FileInput": file_input,
            "CT_ADD_FLDS": [],
        }
        logger.debug(payload)
        # payload = {"Begin_dt": "2024-12-02","End_dt": "2024-12-02","Abspin": 11074,"Duration": 1,"Current_bal": 31.00,"LeaveDescr": "Earned Leave","Absence_Reason": 0,"Partial_Days": "N","Partial_Hours": "","Partial_Hrs1": 0,"Partial_Hrs2": 0,"Comments": "TEST","FileName": "","FileExtn": "","Addattachment": "","FileInput": "","CT_ADD_FLDS": []}  # noqa: E501
        response = requests.post(url, headers=self.headers, json=payload, timeout=TIMEOUT_SECONDS)
        return response.json()

    def get_cancel_absence_details(self, page_load, start_date, end_date, abspin, view_more):  # /hcm/emp/leave/details
        """
        Get cancel absence details.

        :param page_load: Page load indicator.
        :param start_date: Start date (format: 'YYYY-MM-DD').
        :param end_date: End date (format: 'YYYY-MM-DD').
        :param abspin: Absence PIN.
        :param view_more: View more indicator.
        :return: JSON response from the API.
        """
        url = f"{self.base_url}/hcm/emp/leave/details"
        payload = {
            "Page_Load": page_load,
            "Start_Date": start_date,
            "End_Date": end_date,
            "Abspin": abspin,
            "View_More": view_more,
        }
        response = requests.post(url, headers=self.headers, json=payload, timeout=TIMEOUT_SECONDS)
        return response.json()

    def post_cancel_absence_details(
        self, abspin, transaction_nbr, start_date, end_date, duration
    ):  # /hcm/emp/cancel/leave
        """
        Post cancel absence details.

        :param abspin: Absence PIN.
        :param transaction_nbr: Transaction number.
        :param start_date: Start date (format: 'YYYY-MM-DD').
        :param end_date: End date (format: 'YYYY-MM-DD').
        :param duration: Duration.
        :return: JSON response from the API.
        """
        url = f"{self.base_url}/hcm/cancel/leave"
        payload = {
            "Abspin": abspin,
            "Transaction_Nbr": transaction_nbr,
            "Start_Date": start_date,
            "End_Date": end_date,
            "Duration": duration,
        }
        response = requests.post(url, headers=self.headers, json=payload, timeout=TIMEOUT_SECONDS)
        return response.json()


# Example usage:
if __name__ == "__main__":
    START_DATE = "2023-10-01"
    # Use environment variables for client_id, client_secret, and associate_id
    absence_manager = AbsenceManager(client_id=None, client_secret=None, associate_id=None)

    # Get absence types
    absence_types = absence_manager.get_absence_types(START_DATE)
    logger.debug("-----------------------")
    logger.debug("Absence Types: %s", absence_types)

    # Get absence details
    absence_details = absence_manager.get_absence_details(
        start_date="2023-10-01", end_date="2023-10-05", abs_pin="11074", partial_days="N", absence_reason="000"
    )
    logger.debug("-----------------------")
    logger.debug("Absence Details: %s", absence_details)

    # Post absence details
    a_response = absence_manager.post_absence_details(
        begin_dt="2024-11-27",
        end_dt="2024-11-27",
        abs_pin=11074,
        duration=1,
        current_bal=30.00,
        leave_descr="Earned Leave",
        absence_reason=0,
        partial_days="N",
        partial_hours="",
        partial_hrs1=0,
        partial_hrs2=0,
        comments="Kindly reject the leave request. Raised for testing",
        add_attachment="N",
        file_name="",
        file_extn="",
        file_input="",
    )
    logger.debug("-----------------------")
    logger.debug("Post Absence Response: %s", a_response)

    # Get cancel absence details
    cancel_details = absence_manager.get_cancel_absence_details(
        page_load="Y", start_date="", end_date="", abspin=11074, view_more="false"
    )
    logger.debug("-----------------------")
    logger.debug("Cancel Absence Details: %s", cancel_details)

    # Post cancel absence details
    cancel_response = absence_manager.post_cancel_absence_details(
        abspin="11051", transaction_nbr="35366624", start_date="2024-11-08", end_date="2024-11-08", duration="1"
    )
    logger.debug("-----------------------")
    logger.debug("Post Cancel Absence Response: %s", cancel_response)
