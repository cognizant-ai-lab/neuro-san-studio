
class BasePlugin:
    def __init__(self, plugin_name: str, args: dict = None):
        self.plugin_name = plugin_name
        self.args = args or {}

    def pre_server_start_action(self):
        pass

    def post_server_start_action(self):
        pass

    def cleanup(self):
        pass

    def initialize(self):
        """Initialize the plugin. This method is called during server startup."""
        pass

    @staticmethod
    def update_args_dict(args_dict: dict):
        pass

    @staticmethod
    def update_parser_args(parser):
        pass

    def __str__(self):
        return f"{self.plugin_name} Plugin"
    
    def __repr__(self):
        return f"{self.plugin_name} Plugin"
    