# factory_sense/medic/remedy.py
from neuro_san.interfaces.coded_tool import CodedTool
import json
from datetime import datetime
import logging
import boto3
import botocore
import os
import copy

class MedicTool(CodedTool):
    """
    Medic Tool for Industrial IoT Systems
    Provides remedies and fixes for temperature, humidity, pressure, and vibration issues.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.s3 = boto3.client('s3')
        self.bucket_name = 'neuro-san-factory-sense-medic'
        # The SOP file stored in S3 and in-repo is named lowercase 'sop.txt'
        # Keep this in sync with objects uploaded to S3.
        self.sop_key = 'SOP.txt'
        self.local_sop_file = 'SOP.txt'
        self._load_sop_document()
    
    def _load_sop_document(self):
        """Load SOP document from S3 bucket"""
        # Only fetch SOP from S3. Do not fall back to a local file.
        try:
            # Attempt S3 download; if this raises an exception, fail loudly per request.
            self.s3.download_file(self.bucket_name, self.sop_key, self.local_sop_file)
            self.logger.info("SOP document downloaded successfully from S3")

            # Load the downloaded file
            with open(self.local_sop_file, 'r', encoding='utf-8') as f:
                try:
                    self.sop_content = json.load(f)
                    self.logger.info(f"Loaded SOP document from '{self.local_sop_file}'")
                except json.JSONDecodeError as e:
                    self.logger.error(f"Error parsing SOP document from S3 file: {e}")
                    print(f"Error parsing SOP document from S3 file: {e}")
                    self.sop_content = {}
        except botocore.exceptions.ClientError as e:
            # S3 specific client error: print and log the error and do not proceed to local fallback
            self.logger.error(f"Error downloading SOP from S3: {e}")
            print(f"Error downloading SOP from S3: {e}")
            self.sop_content = {}
        except Exception as e:
            # Any other error during download or file operations
            self.logger.error(f"Unexpected error loading SOP from S3: {e}")
            print(f"Unexpected error loading SOP from S3: {e}")
            self.sop_content = {}

    def _get_sop_remedy(self, issue_type, severity):
        """Get remedy from SOP document"""
        try:
            if not self.sop_content:
                self._load_sop_document()
            
            sop_key = f"{issue_type.lower()}_{severity.lower()}"
            if sop_key in self.sop_content:
                # Return a deep copy so we don't mutate the loaded SOP
                return copy.deepcopy(self.sop_content[sop_key])
            else:
                self.logger.warning(f"No SOP found for {sop_key}")
                return None
        except Exception as e:
            self.logger.error(f"Error getting remedy from SOP: {e}")
            return None

    def _generate_remedy(self, machine_id, issue_type, severity, current_metrics, 
                        recommended_actions, trend_analysis, root_cause_analysis, safety_considerations):
        """Generate detailed remedy based on issue type and severity"""
        # Use ONLY SOP entries fetched from S3 as the source of truth for remedies.
        sop_key = f"{issue_type.lower()}_{severity.lower()}"
        sop_remedy = self._get_sop_remedy(issue_type, severity)

        if sop_remedy:
            # Merge contextual fields without mutating the SOP entry (deepcopy returned by _get_sop_remedy)
            sop_remedy.setdefault("root_cause_analysis", {})
            sop_remedy.setdefault("trend_analysis", {})
            sop_remedy.setdefault("current_metrics", {})
            sop_remedy.setdefault("safety_precautions", [])
            sop_remedy.setdefault("immediate_actions", [])

            sop_remedy["root_cause_analysis"] = root_cause_analysis or sop_remedy["root_cause_analysis"]
            sop_remedy["trend_analysis"] = trend_analysis or sop_remedy["trend_analysis"]
            sop_remedy["current_metrics"] = current_metrics or sop_remedy["current_metrics"]

            if safety_considerations:
                sop_remedy["safety_precautions"].extend(safety_considerations)

            if recommended_actions:
                sop_remedy["immediate_actions"].extend(recommended_actions)

            return sop_remedy
        else:
            # No SOP entry found for this key; per request, we do NOT generate hard-coded remedies.
            self.logger.error(f"No SOP entry found for key: {sop_key}")
            print(f"No SOP entry found for key: {sop_key}")
            return {
                "error": "no_sop_entry",
                "sop_key": sop_key,
                "message": "No SOP entry found in S3 for the given issue_type and severity. Please add an entry to sop.txt in the configured S3 bucket."
            }
    
    # NOTE: All hard-coded remedy generation methods have been removed.
    # Medic now relies exclusively on SOP entries fetched from S3 (sop.txt).