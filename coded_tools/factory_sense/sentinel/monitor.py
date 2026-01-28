# factory_sense_new/sentinel/monitor.py
from neuro_san.interfaces.coded_tool import CodedTool
import json
from awscrt import io, mqtt, auth, http
from awsiot import mqtt_connection_builder
import logging
from datetime import datetime
import threading
import time
import os
from dotenv import load_dotenv

# Load environment variables from factory_sense_new specific .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

class SentinelTool(CodedTool):
    """
    Sentinel Tool for Industrial IoT Monitoring
    Monitors machine health from AWS IoT Device Shadow topics.
    Focuses on temperature, pressure, humidity, and vibration parameters.
    ONLY reads MQTT messages - NO decision making.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        self.mqtt_connection = None
        self.is_connected = False
        self.metrics_data_lock = threading.Lock()
        self.latest_metrics_data = None
        
        # Get the factory_sense_new directory path
        factory_sense_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # AWS IoT configuration from environment variables
        self.endpoint = os.getenv("AWS_IOT_ENDPOINT")
        self.client_id = os.getenv("AWS_IOT_CLIENT_ID")
        
        # Resolve relative certificate paths
        cert_path = os.getenv("AWS_IOT_CERT_PATH")
        key_path = os.getenv("AWS_IOT_KEY_PATH")
        root_ca_path = os.getenv("AWS_IOT_ROOT_CA_PATH")
        
        self.cert_path = os.path.join(factory_sense_dir, cert_path) if cert_path else None
        self.key_path = os.path.join(factory_sense_dir, key_path) if key_path else None
        self.root_ca_path = os.path.join(factory_sense_dir, root_ca_path) if root_ca_path else None
        
        # MQTT Topics from environment variables
        self.shadow_get_topic_template = os.getenv("AWS_IOT_SHADOW_GET_TOPIC", "$aws/things/{machine_id}/shadow/get")
        self.shadow_get_accepted_topic_template = os.getenv("AWS_IOT_SHADOW_GET_ACCEPTED_TOPIC", "$aws/things/{machine_id}/shadow/get/accepted")
        
        # Validate that all required environment variables are set
        required_vars = ["AWS_IOT_ENDPOINT", "AWS_IOT_CLIENT_ID", "AWS_IOT_CERT_PATH", "AWS_IOT_KEY_PATH", "AWS_IOT_ROOT_CA_PATH"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            self.logger.warning(f"Missing environment variables: {missing_vars}")
    
    def _on_connection_interrupted(self, connection, error, **kwargs):
        """Callback for connection interrupted"""
        self.logger.warning(f"Connection interrupted: {error}")
        self.is_connected = False
    
    def _on_connection_resumed(self, connection, return_code, session_present, **kwargs):
        """Callback for connection resumed"""
        self.logger.info(f"Connection resumed. Return code: {return_code}, Session present: {session_present}")
        self.is_connected = True
    
    def _on_message_received(self, topic, payload, dup, qos, retain, **kwargs):
        """Callback for message received"""
        try:
            message_data = json.loads(payload.decode('utf-8'))
            self.logger.info(f"Received message on topic {topic}")
            self._process_machine_metrics(message_data, topic)
        except Exception as e:
            self.logger.error(f"Error processing MQTT message: {e}")
    
    def _process_machine_metrics(self, message_data, topic):
        """Process machine metrics message from AWS IoT Device Shadow"""
        try:
            topic_parts = topic.split('/')
            machine_id = topic_parts[2]
            
            if 'state' not in message_data:
                return
            
            state = message_data.get('state', {})
            reported = state.get('reported', {})
            
            # Required fields for the new machine type
            required_fields = ["timestamp", "temperature", "humidity", "pressure", "vibration"]
            if not all(field in reported for field in required_fields):
                self.logger.warning(f"Missing required fields in shadow data: {required_fields}")
                return
            
            with self.metrics_data_lock:
                self.latest_metrics_data = {
                    "machine_id": machine_id,
                    "full_shadow_document": message_data
                }
            
        except Exception as e:
            self.logger.error(f"Error processing machine shadow data: {e}")
    
    def _connect_aws_iot(self):
        """Connect to AWS IoT Core MQTT"""
        try:
            if not os.path.exists(self.cert_path):
                return False
            if not os.path.exists(self.key_path):
                return False
            if not os.path.exists(self.root_ca_path):
                return False
            
            event_loop_group = io.EventLoopGroup(1)
            host_resolver = io.DefaultHostResolver(event_loop_group)
            client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)
            
            self.mqtt_connection = mqtt_connection_builder.mtls_from_path(
                endpoint=self.endpoint,
                cert_filepath=self.cert_path,
                pri_key_filepath=self.key_path,
                client_bootstrap=client_bootstrap,
                ca_filepath=self.root_ca_path,
                client_id=self.client_id,
                clean_session=False,
                keep_alive_secs=30,
                on_connection_interrupted=self._on_connection_interrupted,
                on_connection_resumed=self._on_connection_resumed
            )
            
            connect_future = self.mqtt_connection.connect()
            connect_result = connect_future.result(timeout=10)
            self.is_connected = True
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to AWS IoT: {e}")
            return False
    
    def _subscribe_to_metrics_topic(self, machine_id="test-thing"):
        """Subscribe to AWS IoT Device Shadow response topic"""
        try:
            response_topic = self.shadow_get_accepted_topic_template.format(machine_id=machine_id)
            
            subscribe_future, packet_id = self.mqtt_connection.subscribe(
                topic=response_topic,
                qos=mqtt.QoS.AT_LEAST_ONCE,
                callback=self._on_message_received
            )
            
            subscribe_result = subscribe_future.result(timeout=5)
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to subscribe to topic: {e}")
            return False
    
    def _request_shadow_document(self, machine_id="test-thing"):
        """Request the current shadow document"""
        try:
            request_topic = self.shadow_get_topic_template.format(machine_id=machine_id)
            
            publish_future, packet_id = self.mqtt_connection.publish(
                topic=request_topic,
                payload="{}",
                qos=mqtt.QoS.AT_LEAST_ONCE
            )
            
            publish_result = publish_future.result(timeout=5)
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to request shadow document: {e}")
            return False
    
    def _disconnect_aws_iot(self):
        """Disconnect from AWS IoT"""
        if self.mqtt_connection and self.is_connected:
            try:
                disconnect_future = self.mqtt_connection.disconnect()
                disconnect_future.result(timeout=5)
                self.is_connected = False
            except Exception as e:
                self.logger.error(f"Error disconnecting from AWS IoT: {e}")
    
    def invoke(self, args, sly_data):
        """
        Main function to monitor machine health and return raw data
        NO DECISION MAKING - ONLY DATA RETRIEVAL
        """
        try:
            machine_id = args.get("machine_id", "test-thing")
            timeout = int(args.get("timeout", "30"))
            
            self.logger.info(f"Starting machine monitoring for {machine_id}")
            
            # Connect to AWS IoT
            if not self._connect_aws_iot():
                return {
                    "error": "Failed to connect to AWS IoT",
                    "machine_id": machine_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Subscribe to metrics topic
            if not self._subscribe_to_metrics_topic(machine_id):
                self._disconnect_aws_iot()
                return {
                    "error": "Failed to subscribe to metrics topic",
                    "machine_id": machine_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Request shadow document
            if not self._request_shadow_document(machine_id):
                self._disconnect_aws_iot()
                return {
                    "error": "Failed to request shadow document",
                    "machine_id": machine_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Wait for response with timeout
            start_time = time.time()
            while time.time() - start_time < timeout:
                with self.metrics_data_lock:
                    if self.latest_metrics_data:
                        shadow_document = self.latest_metrics_data["full_shadow_document"]
                        break
                time.sleep(0.1)
            else:
                self._disconnect_aws_iot()
                return {
                    "error": f"Timeout waiting for shadow data after {timeout} seconds",
                    "machine_id": machine_id,
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            # Process the shadow document - ONLY EXTRACT DATA, NO ANALYSIS
            reported = shadow_document.get("state", {}).get("reported", {})
            
            # Extract only the required metrics
            metrics = {
                "temperature": reported.get("temperature"),
                "humidity": reported.get("humidity"),
                "pressure": reported.get("pressure"),
                "vibration": reported.get("vibration")
            }
            
            # Create structured data - NO DECISION MAKING
            structured_data = {
                "machine_id": machine_id,
                "timestamp": reported.get("timestamp", datetime.utcnow().isoformat()),
                "metrics": metrics
            }
            
            self._disconnect_aws_iot()
            
            return {
                "shadow_document": shadow_document,
                "structured_data": structured_data,
                "success": True
            }
            
        except Exception as e:
            self.logger.error(f"Error in invoke: {e}")
            return {
                "error": str(e),
                "machine_id": machine_id,
                "timestamp": datetime.utcnow().isoformat()
            } 