import logging
import os
from copy import deepcopy
from typing import *

from pydantic import BaseModel

from config_wrangler.config_data_loaders.base_config_data_loader import BaseConfigDataLoader
from config_wrangler.utils import walk_model, match_config_data_to_field, has_sub_fields


class EnvConfigDataLoader(BaseConfigDataLoader):
    """
    Copied initial version from Pydantic BaseSettings.
    Made to fit into ConfigLoader approach with nested models.
    """

    def __init__(self, env_prefix: str = None, config_data_dict: Dict[str, Any] = None, **kwargs):
        super().__init__(config_data_dict=config_data_dict, **kwargs)
        self.env_prefix = env_prefix or ''
        self.log = logging.getLogger(__name__)

    def read_config_data(self, model: BaseModel) -> MutableMapping:
        config_data = deepcopy(self._init_config_data)

        env_vars = {k.lower(): v for k, v in os.environ.items()}

        for field_name, field_info, parents in walk_model(model):
            env_val: Optional[str] = None
            # Note: field.field_info.extra['env_names'] is set from the 'env' variable on the field or in Config.
            #       See https://pydantic-docs.helpmanual.io/usage/settings/#environment-variable-names

            field_possible_names = [field_info.serialization_alias, field_info.alias, field_name]

            # Search for env var named directly after the prefix + field (it would apply to that field in ANY section)
            if self.env_prefix is not None and self.env_prefix != '':
                for env_name in field_possible_names:
                    if env_name is not None:
                        env_full_name = f"{self.env_prefix}{env_name}"
                        env_val = env_vars.get(env_full_name.lower())
                        if env_val is not None:
                            break

            if env_val is None:
                possible_name_delim = ('_', '.', ':')
                possible_env_vars = set()

                for field_name_option in field_possible_names:
                    for delimiter in possible_name_delim:
                        if field_name_option:
                            full_name = delimiter.join(parents + [field_name_option])
                        else:
                            full_name = delimiter.join(parents)
                        env_name = f"{self.env_prefix}{full_name}"
                        if env_name in env_vars:
                            possible_env_vars.add(env_name)
                if len(possible_env_vars) > 1:
                    raise ValueError(f"Found multiple matches for {parents} {field_name} {field_info}.  They are: {possible_env_vars}")
                elif len(possible_env_vars) == 1:
                    env_var = list(possible_env_vars)[0]
                    self.log.info(f"Read ENV {env_var} into {parents} {field_name} {field_info}")
                    env_val = env_vars[env_var]

            if has_sub_fields(field_info.annotation):
                env_val = match_config_data_to_field(
                    field_name=field_name,
                    field_info=field_info,
                    field_value=env_val,
                    parent_container={},
                    root_config_data={},
                    parents=parents,
                )

            # Walk down the hierarchy making nodes as needed
            if env_val is not None:
                sub_config = config_data
                for parent in parents:
                    if parent in sub_config:
                        sub_config = sub_config[parent]
                    else:
                        new_sub_config = dict()
                        sub_config[parent] = new_sub_config
                        sub_config = new_sub_config
                # Only set the value if it is not already in our config_data
                if field_name not in sub_config:
                    sub_config[field_name] = env_val
        return config_data
