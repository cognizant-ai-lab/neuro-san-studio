#!/usr/bin/env python3
"""
Test Program for Herald Notification Tool
Tests actual notification sending to AWS IoT Cloud
"""

import json
import sys
import os
from datetime import datetime, timezone
import logging
import time

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the notification tool
from notification import HeraldTool

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NotificationTester:
    """Test class for Herald notification functionality"""
    
    def __init__(self):
        self.herald = HeraldTool()
        self.test_results = []
    
    def check_environment_setup(self):
        """Check if AWS IoT environment is properly configured"""
        print("\n" + "="*60)
        print("CHECKING AWS IOT ENVIRONMENT SETUP")
        print("="*60)
        
        required_vars = [
            "AWS_IOT_ENDPOINT",
            "AWS_IOT_CLIENT_ID", 
            "AWS_IOT_CERT_PATH",
            "AWS_IOT_KEY_PATH",
            "AWS_IOT_ROOT_CA_PATH"
        ]
        
        missing_vars = []
        for var in required_vars:
            value = os.getenv(var)
            if not value:
                missing_vars.append(var)
                print(f"❌ Missing: {var}")
            else:
                print(f"✅ Found: {var} = {value}")
        
        if missing_vars:
            print(f"\n⚠️  Missing environment variables: {missing_vars}")
            print("Please set these environment variables before running the test.")
            return False
        
        # Check if certificate files exist
        cert_path = os.getenv("AWS_IOT_CERT_PATH")
        key_path = os.getenv("AWS_IOT_KEY_PATH")
        root_ca_path = os.getenv("AWS_IOT_ROOT_CA_PATH")
        
        factory_sense_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        cert_file = os.path.join(factory_sense_dir, cert_path) if cert_path else None
        key_file = os.path.join(factory_sense_dir, key_path) if key_path else None
        root_ca_file = os.path.join(factory_sense_dir, root_ca_path) if root_ca_path else None
        
        print(f"\nChecking certificate files:")
        print(f"  Certificate: {cert_file} - {'✅ Exists' if os.path.exists(cert_file) else '❌ Missing'}")
        print(f"  Private Key: {key_file} - {'✅ Exists' if os.path.exists(key_file) else '❌ Missing'}")
        print(f"  Root CA: {root_ca_file} - {'✅ Exists' if os.path.exists(root_ca_file) else '❌ Missing'}")
        
        all_files_exist = all([
            os.path.exists(cert_file) if cert_file else False,
            os.path.exists(key_file) if key_file else False,
            os.path.exists(root_ca_file) if root_ca_file else False
        ])
        
        return all_files_exist
    
    def test_notification_building(self):
        """Test notification message building without sending"""
        print("\n" + "="*60)
        print("TESTING NOTIFICATION MESSAGE BUILDING")
        print("="*60)
        
        test_cases = [
            {
                "name": "Warning Notification",
                "recipient": "technician",
                "notification_type": "warning",
                "title": "Temperature Warning Alert",
                "message": "Machine temperature is above normal threshold",
                "priority": "medium",
                "action_required": True
            },
            {
                "name": "Critical Alert",
                "recipient": "technician,supervisor,maintenance_manager",
                "notification_type": "alert",
                "title": "Critical Humidity Alert",
                "message": "Machine humidity is at critical levels requiring immediate attention",
                "priority": "high",
                "action_required": True
            },
            {
                "name": "Emergency Escalation",
                "recipient": "technician,supervisor,maintenance_manager,emergency_response_team",
                "notification_type": "escalation",
                "title": "Emergency Pressure Alert",
                "message": "Machine pressure is at emergency levels - immediate shutdown required",
                "priority": "urgent",
                "action_required": True
            }
        ]
        
        for test_case in test_cases:
            print(f"\n--- Testing: {test_case['name']} ---")
            
            # Build notification message
            message = self.herald._build_notification_message(
                recipient=test_case["recipient"],
                notification_type=test_case["notification_type"],
                title=test_case["title"],
                message=test_case["message"],
                priority=test_case["priority"],
                action_required=test_case["action_required"]
            )
            
            print(f"✅ Message built successfully")
            print(f"   Recipient: {message['state']['reported']['notification']['recipient']}")
            print(f"   Type: {message['state']['reported']['notification']['notification_type']}")
            print(f"   Priority: {message['state']['reported']['notification']['priority']}")
            print(f"   Title: {message['state']['reported']['notification']['title']}")
            print(f"   Action Required: {message['state']['reported']['notification']['action_required']}")
            
            # Validate message structure
            notification = message['state']['reported']['notification']
            required_fields = ['recipient', 'notification_type', 'title', 'message', 'priority', 'action_required', 'timestamp', 'source']
            
            missing_fields = [field for field in required_fields if field not in notification]
            if missing_fields:
                print(f"❌ Missing fields: {missing_fields}")
            else:
                print(f"✅ All required fields present")
    
    def test_aws_iot_connection(self):
        """Test AWS IoT connection without sending notifications"""
        print("\n" + "="*60)
        print("TESTING AWS IOT CONNECTION")
        print("="*60)
        
        try:
            print("Attempting to connect to AWS IoT...")
            success = self.herald._connect_aws_iot()
            
            if success:
                print("✅ Successfully connected to AWS IoT")
                print(f"   Connection status: {self.herald.is_connected}")
                
                # Test disconnection
                print("Testing disconnection...")
                self.herald._disconnect_aws_iot()
                print("✅ Successfully disconnected from AWS IoT")
                return True
            else:
                print("❌ Failed to connect to AWS IoT")
                return False
                
        except Exception as e:
            print(f"❌ Connection test failed with error: {e}")
            return False
    
    def test_notification_sending(self):
        """Test actual notification sending to AWS IoT"""
        print("\n" + "="*60)
        print("TESTING NOTIFICATION SENDING TO AWS IOT")
        print("="*60)
        
        test_cases = [
            {
                "name": "Test Warning Notification",
                "args": {
                    "recipient": "technician",
                    "notification_type": "warning",
                    "title": "Test Temperature Warning",
                    "message": "This is a test warning notification from Factory Sense New",
                    "priority": "medium",
                    "channels": ["aws_iot"],
                    "action_required": True
                }
            },
            {
                "name": "Test Critical Alert",
                "args": {
                    "recipient": "technician,supervisor,maintenance_manager",
                    "notification_type": "alert",
                    "title": "Test Critical Humidity Alert",
                    "message": "This is a test critical alert from Factory Sense New",
                    "priority": "high",
                    "channels": ["aws_iot"],
                    "action_required": True
                }
            },
            {
                "name": "Test Emergency Escalation",
                "args": {
                    "recipient": "technician,supervisor,maintenance_manager,emergency_response_team",
                    "notification_type": "escalation",
                    "title": "Test Emergency Pressure Alert",
                    "message": "This is a test emergency escalation from Factory Sense New",
                    "priority": "urgent",
                    "channels": ["aws_iot"],
                    "action_required": True
                }
            }
        ]
        
        results = []
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n--- Test {i}: {test_case['name']} ---")
            print(f"Recipient: {test_case['args']['recipient']}")
            print(f"Type: {test_case['args']['notification_type']}")
            print(f"Priority: {test_case['args']['priority']}")
            
            try:
                # Send notification
                result = self.herald.invoke(test_case['args'], {})
                
                if result.get("success"):
                    print("✅ Notification sent successfully!")
                    print(f"   Timestamp: {result.get('timestamp')}")
                    results.append(True)
                else:
                    print(f"❌ Notification failed: {result.get('error')}")
                    results.append(False)
                
                # Add delay between notifications
                if i < len(test_cases):
                    print("   Waiting 2 seconds before next notification...")
                    time.sleep(2)
                    
            except Exception as e:
                print(f"❌ Test failed with exception: {e}")
                results.append(False)
        
        success_count = sum(results)
        total_count = len(results)
        
        print(f"\n--- Notification Sending Summary ---")
        print(f"Successful: {success_count}/{total_count}")
        print(f"Success Rate: {(success_count/total_count)*100:.1f}%")
        
        return success_count == total_count
    
    def test_notification_with_different_priorities(self):
        """Test notifications with different priority levels"""
        print("\n" + "="*60)
        print("TESTING NOTIFICATIONS WITH DIFFERENT PRIORITIES")
        print("="*60)
        
        priorities = ["low", "medium", "high", "urgent"]
        
        for priority in priorities:
            print(f"\n--- Testing {priority.upper()} priority notification ---")
            
            args = {
                "recipient": "technician",
                "notification_type": "test",
                "title": f"Test {priority.title()} Priority Notification",
                "message": f"This is a test notification with {priority} priority from Factory Sense New",
                "priority": priority,
                "channels": ["aws_iot"],
                "action_required": True
            }
            
            try:
                result = self.herald.invoke(args, {})
                
                if result.get("success"):
                    print(f"✅ {priority.title()} priority notification sent successfully")
                else:
                    print(f"❌ {priority.title()} priority notification failed: {result.get('error')}")
                    
            except Exception as e:
                print(f"❌ {priority.title()} priority test failed: {e}")
            
            # Small delay between tests
            time.sleep(1)
    
    def test_error_handling(self):
        """Test error handling with invalid inputs"""
        print("\n" + "="*60)
        print("TESTING ERROR HANDLING")
        print("="*60)
        
        error_test_cases = [
            {
                "name": "Missing Recipient",
                "args": {
                    "notification_type": "warning",
                    "title": "Test Warning",
                    "message": "Test message",
                    "priority": "medium"
                }
            },
            {
                "name": "Invalid Priority",
                "args": {
                    "recipient": "technician",
                    "notification_type": "warning",
                    "title": "Test Warning",
                    "message": "Test message",
                    "priority": "invalid_priority"
                }
            },
            {
                "name": "Empty Message",
                "args": {
                    "recipient": "technician",
                    "notification_type": "warning",
                    "title": "Test Warning",
                    "message": "",
                    "priority": "medium"
                }
            }
        ]
        
        for test_case in error_test_cases:
            print(f"\n--- Testing: {test_case['name']} ---")
            
            try:
                result = self.herald.invoke(test_case['args'], {})
                
                if result.get("success"):
                    print(f"⚠️  Unexpected success for error case: {test_case['name']}")
                else:
                    print(f"✅ Correctly handled error: {result.get('error')}")
                    
            except Exception as e:
                print(f"✅ Correctly caught exception: {e}")
    
    def run_comprehensive_test(self):
        """Run comprehensive notification testing"""
        print("FACTORY SENSE NEW - HERALD NOTIFICATION TEST SUITE")
        print("="*80)
        print(f"Test started at: {datetime.now(timezone.utc).isoformat()}")
        
        # Step 1: Check environment setup
        env_ok = self.check_environment_setup()
        if not env_ok:
            print("\n❌ Environment setup check failed. Cannot proceed with cloud tests.")
            print("Please configure AWS IoT environment variables and certificates.")
            return False
        
        # Step 2: Test notification building
        self.test_notification_building()
        
        # Step 3: Test AWS IoT connection
        connection_ok = self.test_aws_iot_connection()
        if not connection_ok:
            print("\n❌ AWS IoT connection failed. Cannot proceed with sending tests.")
            return False
        
        # Step 4: Test notification sending
        sending_ok = self.test_notification_sending()
        
        # Step 5: Test different priorities
        self.test_notification_with_different_priorities()
        
        # Step 6: Test error handling
        self.test_error_handling()
        
        # Final summary
        print(f"\n{'='*80}")
        print("TEST SUMMARY")
        print(f"{'='*80}")
        print(f"Environment Setup: {'✅ PASS' if env_ok else '❌ FAIL'}")
        print(f"AWS IoT Connection: {'✅ PASS' if connection_ok else '❌ FAIL'}")
        print(f"Notification Sending: {'✅ PASS' if sending_ok else '❌ FAIL'}")
        print(f"Test completed at: {datetime.now(timezone.utc).isoformat()}")
        
        return env_ok and connection_ok and sending_ok

def main():
    """Main test function"""
    try:
        tester = NotificationTester()
        success = tester.run_comprehensive_test()
        
        if success:
            print("\n🎉 All notification tests passed!")
            return 0
        else:
            print("\n❌ Some notification tests failed!")
            return 1
            
    except Exception as e:
        print(f"❌ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
