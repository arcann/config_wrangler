from pydantic import PrivateAttr

from config_wrangler.config_templates.config_hierarchy import ConfigHierarchy


class DynamicallyReferenced(ConfigHierarchy):
    config_source_name: str = "Anonymous"

    def __str__(self):
        return self.config_source_name
