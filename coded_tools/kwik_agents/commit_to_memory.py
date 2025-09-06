import json
import logging
import os
from datetime import datetime
from typing import Any
from typing import Dict

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.kwik_agents.list_topics import LONG_TERM_MEMORY_FILE
from coded_tools.kwik_agents.list_topics import MEMORY_DATA_STRUCTURE
from coded_tools.kwik_agents.list_topics import MEMORY_FILE_PATH


class CommitToMemory(CodedTool):
    """
    A CodedTool that saves facts related to a topic to memory.
    """

    def __init__(self):
        self.topic_memory = None

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "new_fact" a brief description of the new fact to remember.
                    "topic" a topic for this new fact to be stored under.

        :param sly_data: A dictionary whose keys are defined by the agent hierarchy,
                but whose values are meant to be kept out of the chat stream.

                This dictionary is largely to be treated as read-only.
                It is possible to add key/value pairs to this dict that do not
                yet exist as a bulletin board, as long as the responsibility
                for which coded_tool publishes new entries is well understood
                by the agent chain implementation and the coded_tool implementation
                adding the data is not invoke()-ed more than once.

                Keys expected for this implementation are:
                    "TopicMemory" a dictionary containing topics as keys and strings of facts as values.

        :return:
            In case of successful execution:
                The full agent network as a string.
            otherwise:
                a text string an error message in the format:
                "Error: <error message>"
        """
        self.topic_memory = sly_data.get(MEMORY_DATA_STRUCTURE, None)
        if not self.topic_memory:
            if LONG_TERM_MEMORY_FILE:
                self.read_memory_from_file()
            else:
                self.topic_memory = {}
        the_new_fact: str = args.get("new_fact", "")
        if the_new_fact == "":
            return "Error: No new_fact provided."
        the_topic: str = args.get("topic", "")
        if the_topic == "":
            return "Error: No topic provided."

        logger = logging.getLogger(self.__class__.__name__)
        logger.info(">>>>>>>>>>>>>>>>>>>CommitToMemory>>>>>>>>>>>>>>>>>>")
        logger.info("New Fact: %s", str(the_new_fact))
        logger.info("Topic: %s", str(the_topic))
        the_memory_str = self.add_memory(the_topic, the_new_fact)
        logger.info("Memory on this topic: \n %s", str(the_memory_str))
        sly_data[MEMORY_DATA_STRUCTURE] = self.topic_memory
        logger.info(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        return the_memory_str

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        Delegates to the synchronous invoke method for now.
        """
        return self.invoke(args, sly_data)

    def write_memory_to_file(self):
        """
        Writes the topic memory dictionary to a JSON file.
        """
        file_path = MEMORY_FILE_PATH + MEMORY_DATA_STRUCTURE + ".json"
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(json.dumps(self.topic_memory, indent=2))

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

    def add_memory(self, topic: str, new_fact: str) -> str:
        """
        Adds a new fact to memory and saves the memory dictionary to a JSON file.

        Parameters:
        - topic (str): A topic to store the memory under.
        - new_fact (str): The new fact to remember.

        Returns:
        - str: The updated memory string for the given topic.
        """

        time_stamp = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "

        if topic not in self.topic_memory or not self.topic_memory[topic]:
            self.topic_memory[topic] = time_stamp + new_fact
        else:
            self.topic_memory[topic] = self.topic_memory[topic] + "\n" + time_stamp + new_fact

        if LONG_TERM_MEMORY_FILE:
            self.write_memory_to_file()

        return self.topic_memory[topic]
