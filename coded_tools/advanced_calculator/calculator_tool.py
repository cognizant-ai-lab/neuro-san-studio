# Copyright (C) 2023-2025 Cognizant Digital Business, Evolutionary AI.
# All Rights Reserved.
# Issued under the Academic Public License.
#
# You can be released from the terms, and requirements of the Academic Public
# License by purchasing a commercial license.
# Purchase of a commercial license is mandatory for any use of the
# neuro-san-studio SDK Software in commercial settings.
#
import json
import logging
import math
from typing import Any
from typing import Dict
from typing import Union

from neuro_san.interfaces.coded_tool import CodedTool

# Configure default logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CalculatorCodedTool(CodedTool):
    """A dynamically built calculator tool using Python's math library, following the CodedTool structure."""

    def __init__(self):
        """Initialize the Calculator CodedTool."""
        logger.info("CalculatorCodedTool initialized")

        # Define available operations, each mapped to a two-element list:
        # [expected number of arguments, function]
        self.MATH_FUNCTIONS = {
            "add": [2, lambda a, b: a + b],
            "subtract": [2, lambda a, b: a - b],
            "multiply": [2, lambda a, b: a * b],
            "divide": [2, lambda a, b: a / b if b != 0 else "Error: Division by zero"],
            "exponentiate": [2, math.pow],
            "factorial": [
                1,
                lambda n: (math.factorial(int(n)) if n >= 0 else "Error: Factorial of negative numbers is undefined"),
            ],
            "isprime": [
                1,
                lambda n: all(n % i != 0 for i in range(2, int(math.sqrt(n)) + 1)) and n > 1,
            ],
            "squareroot": [
                1,
                lambda n: (math.sqrt(n) if n >= 0 else "Error: Square root of negative numbers is undefined"),
            ],
            "log": [
                1,
                lambda x, base=math.e: (
                    math.log(x, base) if x > 0 else "Error: Logarithm undefined for non-positive values"
                ),
            ],
            "log10": [
                1,
                lambda x: (math.log10(x) if x > 0 else "Error: Logarithm undefined for non-positive values"),
            ],
            "log2": [
                1,
                lambda x: (math.log2(x) if x > 0 else "Error: Logarithm undefined for non-positive values"),
            ],
            "sin": [1, math.sin],
            "cos": [1, math.cos],
            "tan": [
                1,
                lambda x: (math.tan(x) if (x % (math.pi / 2)) != 0 else "Error: Tangent undefined at π/2 + kπ"),
            ],
            "asin": [
                1,
                lambda x: (math.asin(x) if -1 <= x <= 1 else "Error: Input out of domain for arcsin"),
            ],
            "acos": [
                1,
                lambda x: (math.acos(x) if -1 <= x <= 1 else "Error: Input out of domain for arccos"),
            ],
            "atan": [1, math.atan],
            "sinh": [1, math.sinh],
            "cosh": [1, math.cosh],
            "tanh": [1, math.tanh],
            "gcd": [2, lambda a, b: math.gcd(int(a), int(b))],
            "lcm": [
                2,
                lambda a, b: (abs(int(a) * int(b)) // math.gcd(int(a), int(b)) if a and b else 0),
            ],
            "mod": [2, lambda a, b: a % b if b != 0 else "Error: Modulo by zero"],
            "ceil": [1, math.ceil],
            "floor": [1, math.floor],
            "round": [1, round],
            "abs": [1, abs],
            "hypot": [2, math.hypot],
            "degrees": [1, math.degrees],
            "radians": [1, math.radians],
        }

    def process_operation(self, operation: str, operands: list) -> Union[str, float]:
        """
        Processes an operation dynamically.

        For operations that receive more operands than required, this method reduces the operand list
        recursively by applying the function to the first N operands (where N is the expected count)
        and then prepending the intermediate result to the remaining operands.
        """
        # If the operation is a single one (no underscores), handle it directly.
        if "_" not in operation:
            if operation not in self.MATH_FUNCTIONS:
                return f"Error: Unsupported operation '{operation}'"
            required, func = self.MATH_FUNCTIONS[operation]
            if len(operands) > required:
                try:
                    intermediate = func(*operands[:required])
                except Exception as e:
                    return f"Error: {str(e)}"
                # Combine the intermediate result with the remaining operands.
                operands = [intermediate] + operands[required:]
            try:
                return func(*operands)
            except Exception as e:
                return f"Error: {str(e)}"

        # For composite operations (with underscores), split into sub-operations.
        sub_operations = operation.split("_")
        result = operands

        # Process each sub-operation in reverse order (innermost operation first).
        for sub_op in reversed(sub_operations):
            if sub_op not in self.MATH_FUNCTIONS:
                return f"Error: Unsupported operation '{sub_op}'"
            required, func = self.MATH_FUNCTIONS[sub_op]
            if len(result) > required:
                try:
                    intermediate = func(*result[:required])
                except Exception as e:
                    return f"Error: {str(e)}"
                result = [intermediate] + result[required:]
            else:
                try:
                    result = [func(*result)]
                except Exception as e:
                    return f"Error: {str(e)}"
        return result[0]  # Final computed result

    def invoke(self, args: Dict[str, Any], sly_data: Dict[str, Any]) -> Union[Dict[str, Any], str]:
        """
        Execute the requested mathematical operation, supporting multi-step calculations.

        :param args: A dictionary containing:
            - "operation": The mathematical operation to perform (e.g., "log_sin_squareroot_divide_exponentiate").
            - "operands": A list of numbers to perform the operation on.
        :param sly_data: Additional context information (unused here).
        :return: A dictionary with the operation result or an error message.
        """
        logger.info(f"********** {self.__class__.__name__} started **********")
        print(f"args: {args}\n")
        operation = args.get("operation")
        operands = args.get("operands", [])
        if not operation:
            logger.error("Missing operation in request")
            return json.dumps({"error": "Missing operation"})
        result = self.process_operation(operation, operands)
        logger.info(f"Performed {operation} on {operands} -> Result: {result}")
        logger.info(f"********** {self.__class__.__name__} completed **********")
        return {"operation": operation, "result": result}
