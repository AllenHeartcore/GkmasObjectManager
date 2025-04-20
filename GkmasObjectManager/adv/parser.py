"""
adv/parser.py
Parsing raw adventure strings into a dictionary of commands.
"""

import re
import json


# more like a collection of functions than a class
class GkadvCommandParser:

    def _parse_structure(self, string: str) -> dict:
        # assumes NO [] around the string,
        # in order to "peel" nested structures layer by layer

        # str.split() also matches newlines in long messages
        fields = re.split(r" +", string.strip())
        cmd = {"cmd": fields[0]}
        idx = 1  # don't use for loop, since the recursive case does multiple increments

        while idx < len(fields):
            field = fields[idx]

            if "=" not in field:  # e.g., "Variant" in prop
                if "flags" not in cmd:
                    cmd["flags"] = []
                cmd["flags"].append(field)
                idx += 1
                continue

            key, value = re.split(r"(?<!\\)=", field, maxsplit=1)
            # escapes text formats like superscript (<r\=...>...</r>) and emphasis (<em\=>...</em>);
            # r"[^\\]=" would consume the first character in key, so we use negative lookbehind;
            # maxsplit=1 ensures validity, but prevents ValueError if there are multiple "="s

            if value.startswith("\\{") and value.endswith("\\}"):
                value = json.loads(value.replace("\\", ""))
                # we only remove backslashes from "verified" dict strings,
                # or else the newlines & emphasis in long messages will be lost
            elif value.startswith("["):
                subfields = [value]
                while not subfields[-1].endswith("]"):
                    idx += 1
                    subfields.append(fields[idx])
                substring = " ".join(subfields)
                value = self._parse_structure(substring[1:-1])  # recursion
            # else, record value as is

            if key not in cmd:
                cmd[key] = value
            else:
                if not isinstance(cmd[key], list):
                    cmd[key] = [cmd[key]]
                cmd[key].append(value)

            idx += 1

        return cmd

    def process(self, string: str) -> dict:
        string = string.strip()  # remove trailing newlines
        assert string.startswith("[") and string.endswith("]")  # initial check
        return self._parse_structure(string[1:-1])
