import logging
import os
from copy import deepcopy
from typing import *

from pydantic import BaseModel

from config_wrangler.config_data_loaders.base_config_data_loader import BaseConfigDataLoader
from config_wrangler.utils import walk_model, match_config_data_to_field


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

        for field, parents in walk_model(model):
            env_val: Optional[str] = None
            # Note: field.field_info.extra['env_names'] is set from the 'env' variable on the field or in Config.
            #       See https://pydantic-docs.helpmanual.io/usage/settings/#environment-variable-names
            if 'env_names' in field.field_info.extra:
                for env_name in field.field_info.extra['env_names']:
                    env_name = self.env_prefix + env_name
                    env_val = env_vars.get(env_name.lower())
                    if env_val is not None:
                        break

            possible_names = ('_', '.', ':')

            if env_val is None:
                possible_env_vars = set()

                for field_name in [field.alias, field.name]:
                    for delimiter in possible_names:
                        if field_name:
                            full_name = delimiter.join(parents + [field_name])
                        else:
                            full_name = delimiter.join(parents)
                        env_name = f"{self.env_prefix}{full_name}"
                        if env_name in env_vars:
                            possible_env_vars.add(env_name)
                if len(possible_env_vars) > 1:
                    raise ValueError(f"Found multiple matches for {parents} {field}.  They are: {possible_env_vars}")
                elif len(possible_env_vars) == 1:
                    env_var = list(possible_env_vars)[0]
                    self.log.info(f"Read ENV {env_var} into {parents} {field}.")
                    env_val = env_vars[env_var]

            if field.is_complex():
                env_val = match_config_data_to_field(
                    field=field,
                    field_value=env_val,
                    create_from_section_names=False,  # Not yet supported for env
                    parent_container={},
                    root_config_data={},
                    parents=parents
                )

            # Only set the value if it is not already in our config_data
            if env_val is not None:
                sub_config = config_data
                for parent in parents:
                    if parent in sub_config:
                        sub_config = sub_config[parent]
                    else:
                        new_sub_config = dict()
                        sub_config[parent] = new_sub_config
                        sub_config = new_sub_config
                if field.alias not in sub_config:
                    sub_config[field.alias] = env_val
        return config_data
