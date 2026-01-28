# factory_sense_new/herald/notification.py
from neuro_san.interfaces.coded_tool import CodedTool
import json
from awscrt import io, mqtt, auth, http
from awsiot import mqtt_connection_builder
import logging
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

# Load environment variables from factory_sense_new specific .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

class HeraldTool(CodedTool):
    """
    Herald Tool for Industrial IoT Monitoring
    Delivers important messages and notifications via AWS IoT Device Shadow.
    Focuses on temperature, humidity, pressure, and vibration alerts.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        self.mqtt_connection = None
        self.is_connected = False
        
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
        self.notification_topic = os.getenv("AWS_IOT_NOTIFICATION_TOPIC", "$aws/things/test-thing/shadow/name/notification/update")
        
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
    
    def _connect_aws_iot(self):
        """Connect to AWS IoT Core MQTT"""
        try:
            if not os.path.exists(self.cert_path):
                self.logger.error(f"Certificate file not found: {self.cert_path}")
                return False
            if not os.path.exists(self.key_path):
                self.logger.error(f"Private key file not found: {self.key_path}")
                return False
            if not os.path.exists(self.root_ca_path):
                self.logger.error(f"Root CA file not found: {self.root_ca_path}")
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
            self.logger.info("Successfully connected to AWS IoT")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to AWS IoT: {e}")
            return False
    
    def _disconnect_aws_iot(self):
        """Disconnect from AWS IoT"""
        if self.mqtt_connection and self.is_connected:
            try:
                disconnect_future = self.mqtt_connection.disconnect()
                disconnect_future.result(timeout=5)
                self.is_connected = False
                self.logger.info("Successfully disconnected from AWS IoT")
            except Exception as e:
                self.logger.error(f"Error disconnecting from AWS IoT: {e}")
    
    def _build_notification_message(self, recipient: str, notification_type: str, 
                                  title: str, message: str, priority: str, 
                                  action_required: bool) -> dict:
        """Build AWS IoT Device Shadow notification message"""
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Simple notification structure for AWS IoT Device Shadow
        shadow_message = {
            "state": {
                "reported": {
                    "notification": {
                        "recipient": recipient,
                        "notification_type": notification_type,
                        "title": title,
                        "message": message,
                        "priority": priority,
                        "action_required": action_required,
                        "timestamp": timestamp,
                        "source": "factory_sense_herald"
                    },
                    "timestamp": timestamp,
                    "status": "notification_sent"
                }
            }
        }
        
        return shadow_message
    
    def _send_notification(self, recipient: str, notification_type: str, 
                          title: str, message: str, priority: str, 
                          action_required: bool) -> bool:
        """Send notification via AWS IoT Device Shadow"""
        try:
            if not self._connect_aws_iot():
                self.logger.error("Failed to connect to AWS IoT")
                return False
            
            # Build notification message
            notification_message = self._build_notification_message(
                recipient, notification_type, title, message, priority, action_required
            )
            
            # Publish to notification topic
            publish_future, packet_id = self.mqtt_connection.publish(
                topic=self.notification_topic,
                payload=json.dumps(notification_message),
                qos=mqtt.QoS.AT_LEAST_ONCE
            )
            
            publish_result = publish_future.result(timeout=5)
            self.logger.info(f"Notification sent successfully to {recipient}")
            self.logger.info(f"Published to topic: {self.notification_topic}")
            self.logger.info(f"Packet ID: {packet_id}")
            
            self._disconnect_aws_iot()
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send notification: {e}")
            self._disconnect_aws_iot()
            return False
    
    def invoke(self, args, sly_data):
        """
        Main function to send notifications
        """
        try:
            recipient = args.get("recipient")
            notification_type = args.get("notification_type")
            title = args.get("title")
            message = args.get("message")
            priority = args.get("priority")
            channels = args.get("channels", ["aws_iot"])
            action_required = args.get("action_required", True)
            
            self.logger.info(f"Sending {notification_type} notification to {recipient}")
            
            # Send notification
            success = self._send_notification(
                recipient, notification_type, title, message, priority, action_required
            )
            
            if success:
                return {
                    "success": True,
                    "recipient": recipient,
                    "notification_type": notification_type,
                    "priority": priority,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            else:
                return {
                    "error": "Failed to send notification",
                    "recipient": recipient,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            
        except Exception as e:
            self.logger.error(f"Error in invoke: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            } 