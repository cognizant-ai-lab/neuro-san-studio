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
import asyncio
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
        self.math_functions = {
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

    # pylint: disable=too-many-return-statements
    def process_operation(self, operation: str, operands: list) -> Union[str, float]:
        """
        Processes an operation dynamically.

        For operations that receive more operands than required, this method reduces the operand list
        recursively by applying the function to the first N operands (where N is the expected count)
        and then prepending the intermediate result to the remaining operands.
        """
        # If the operation is a single one (no underscores), handle it directly.
        if "_" not in operation:
            if operation not in self.math_functions:
                return f"Error: Unsupported operation '{operation}'"
            required, func = self.math_functions[operation]
            if len(operands) > required:
                try:
                    intermediate = func(*operands[:required])
                except (ValueError, TypeError, ZeroDivisionError, OverflowError, ArithmeticError) as e:
                    return f"Error: {str(e)}"
                # Combine the intermediate result with the remaining operands.
                operands = [intermediate] + operands[required:]
            try:
                return func(*operands)
            except (ValueError, TypeError, ZeroDivisionError, OverflowError, ArithmeticError) as e:
                return f"Error: {str(e)}"

        # For composite operations (with underscores), split into sub-operations.
        sub_operations = operation.split("_")
        result = operands

        # Process each sub-operation in reverse order (innermost operation first).
        for sub_op in reversed(sub_operations):
            if sub_op not in self.math_functions:
                return f"Error: Unsupported operation '{sub_op}'"
            required, func = self.math_functions[sub_op]
            if len(result) > required:
                try:
                    intermediate = func(*result[:required])
                except (ValueError, TypeError, ZeroDivisionError, OverflowError, ArithmeticError) as e:
                    return f"Error: {str(e)}"
                result = [intermediate] + result[required:]
            else:
                try:
                    result = [func(*result)]
                except (ValueError, TypeError, ZeroDivisionError, OverflowError, ArithmeticError) as e:
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
        logger.info("********** %s started **********", self.__class__.__name__)
        logger.debug("args: %s", args)
        operation = args.get("operation")
        operands = args.get("operands", [])
        if not operation:
            logger.error("Missing operation in request")
            return json.dumps({"error": "Missing operation"})
        result = self.process_operation(operation, operands)
        logger.info("Performed %s on %s -> Result: %s", operation, operands, result)
        logger.info("********** %s completed **********", self.__class__.__name__)
        return {"operation": operation, "result": result}

    async def async_invoke(self, args: dict[str, Any], sly_data: dict[str, Any]) -> Union[dict[str, Any], str]:
        """
        Run self.invoke(args, sly_data) in a thread so it won’t block the async event loop, and wait for it to finish
        """
        return await asyncio.to_thread(self.invoke, args, sly_data)
