import logging
from typing import Any
from typing import Dict

from neuro_san.interfaces.coded_tool import CodedTool

from coded_tools.kwik_agents.list_topics import MEMORY_DATA_STRUCTURE


class RecallMemory(CodedTool):
    """
    A CodedTool that retrieves facts related to a topic from memory.
    """

    def __init__(self):
        self.topic_memory = None

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        :param args: An argument dictionary whose keys are the parameters
                to the coded tool and whose values are the values passed for them
                by the calling agent.  This dictionary is to be treated as read-only.

                The argument dictionary expects the following keys:
                    "topic" A topic for which to retrieve relevant facts.

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
            return "NO TOPICS YET!"
        the_topic: str = args.get("topic", "")
        if the_topic == "":
            return "Error: No topic provided."

        logger = logging.getLogger(self.__class__.__name__)
        logger.info(">>>>>>>>>>>>>>>>>>>RecallMemory>>>>>>>>>>>>>>>>>>")
        logger.info("Topic: %s", str(the_topic))
        the_memory_str = self.recall_memory(the_topic)
        logger.info("Memories on this topic: \n %s", str(the_memory_str))
        sly_data[MEMORY_DATA_STRUCTURE] = self.topic_memory
        logger.info(">>>>>>>>>>>>>>>>>>>DONE !!!>>>>>>>>>>>>>>>>>>")
        return the_memory_str

    async def async_invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> str:
        """
        Delegates to the synchronous invoke method for now.
        """
        return self.invoke(args, sly_data)

    def recall_memory(self, topic: str) -> str:
        """
        Recall all facts related to this topic from memory.

        Parameters:
        - topic (str): A topic to retrieve memories for.

        Returns:
        - str: The list of memories related to the topic, or an empty string if the topic doesn't exist.
        """
        if topic in self.topic_memory:
            return self.topic_memory[topic]
        return "NO RELATED MEMORIES!"
