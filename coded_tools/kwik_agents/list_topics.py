import json
import logging
import os
from typing import Any
from typing import Dict

from neuro_san.interfaces.coded_tool import CodedTool

LONG_TERM_MEMORY_FILE = True  # Store and read memory from file
MEMORY_FILE_PATH = "./"
MEMORY_DATA_STRUCTURE = "TopicMemory"


class ListTopics(CodedTool):
    """
    A CodedTool that retrieves and returns the list of topics in the memory.
    """

    def __init__(self):
        self.topic_memory = None

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        :param args: None

        :param sly_data: "TopicMemory" a dictionary containing topics as keys and strings of facts as values.

        :return: The list of topics in the memory
        """
        self.topic_memory = sly_data.get(MEMORY_DATA_STRUCTURE, None)
        if not self.topic_memory:
            if LONG_TERM_MEMORY_FILE:
                self.read_memory_from_file()
            else:
                return "NO TOPICS YET!"

        logger = logging.getLogger(self.__class__.__name__)
        logger.info(">>>>>>>>>>>>>>>>>>>ListTopics>>>>>>>>>>>>>>>>>>")
        topics_str = self.get_memory_topics()
        logger.info("The resulting list of topics: \n %s", str(topics_str))
        sly_data[MEMORY_DATA_STRUCTURE] = self.topic_memory
        logger.info(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        return topics_str

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        Delegates to the synchronous invoke method for now.
        """
        return self.invoke(args, sly_data)

    def read_memory_from_file(self):
        """
        Reads the topic memory dictionary from a JSON file if it exists.
        Otherwise initializes an empty dictionary.
        """
        file_path = MEMORY_FILE_PATH + MEMORY_DATA_STRUCTURE + ".json"
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as file:
                content = file.read()
                self.topic_memory = json.loads(content) if content else {}
        else:
            self.topic_memory = {}

    def get_memory_topics(self) -> str:
        """
        Retrieves the full list of memory topics.

        Returns:
        - list: A sorted list of all memory topics.
        """
        return str(sorted(list(self.topic_memory.keys())))
