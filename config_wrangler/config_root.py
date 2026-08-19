import inspect
import logging
import sys
import typing
import warnings
from pathlib import Path
from typing import List, Any, Self

from pydantic import PrivateAttr, BaseModel

if typing.TYPE_CHECKING:
    from config_wrangler.config_data_loaders.base_config_data_loader import BaseConfigDataLoader
from config_wrangler.config_templates.config_hierarchy import ConfigHierarchy
from config_wrangler.config_templates.credentials import PasswordDefaults
from config_wrangler.config_wrangler_config import ConfigWranglerConfig
from config_wrangler.utils import merge_configs, process_inheritance, process_errors_list, interpolate_values

private_attrs = ('_root_config', '_parents', '_name_map')


class ConfigRoot(ConfigHierarchy):
    """
    The root member of a hierarchy of configuration items.

    NOTE: Children config items should be instances of
    :py:class:`config_wrangler.config_templates.config_hierarchy.ConfigHierarchy`
    """
    model_config = ConfigWranglerConfig(
        validate_default=True,
        validate_assignment=True,
        validate_credentials=True
    )

    _fill_done: bool = PrivateAttr(default=False)
    # _model_validators: PrivateAttr(default=[])

    passwords: PasswordDefaults = PasswordDefaults()
    """
    Default configuration for passwords within this config hierarchy.
    """

    # noinspection PyMethodParameters
    def __init__(__pydantic_self__, **data: Any) -> None:
        log = logging.getLogger(__name__)
        log.debug(f"Calling pydantic __init__")
        super().__init__(**data)
        log.debug("Calling validate_model / fill_hierarchy to fill in root and parent data")
        __pydantic_self__.validate_model()

    def fill_hierarchy_any_type(
            self,
            value: object,
            parents: List[str],
            errors: set,
    ):
        if isinstance(value, BaseModel):
            self.fill_hierarchy(
                model_level=value,
                parents=parents,
                errors=errors
            )
        elif isinstance(value, list):
            for index, entry in enumerate(value):
                self.fill_hierarchy_any_type(
                    value=entry,
                    parents=parents + [f"[{index}]"],
                    errors=errors
                )
        elif isinstance(value, dict):
            for key, entry in value.items():
                self.fill_hierarchy_any_type(
                    value=entry,
                    parents=parents + [f"[{key}]"],
                    errors=errors
                )

    def fill_hierarchy(
            self,
            model_level: BaseModel,
            parents: List[str],
            errors: set,
    ):
        self._fill_done = True
        log = logging.getLogger(__name__)
        if len(parents) > 10:
            raise ValueError(f"Possible model self reference {parents}")
        try:
            model_level._root_config = self
            model_level._parents = parents
            # noinspection PyUnresolvedReferences
            name = model_level.full_item_name()
            log.debug(f"fill_hierarchy on {name}")
        except AttributeError as e:
            log.warning(f"{parents} {repr(model_level)} is not an instance inheriting from ConfigHierarchy: {e}")
        # noinspection PyTypeChecker
        for attr_name in model_level.__class__.model_fields:
            attr_value = getattr(model_level, attr_name)
            self.fill_hierarchy_any_type(
                value=attr_value,
                parents=parents + [attr_name],
                errors=errors
            )

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                # Note: getmembers_static avoids calling property methods like getmembers does
                method_list = inspect.getmembers_static(model_level, predicate=inspect.ismethod)
            except Exception:
                method_list = []
        for validation_method_name, validation_method in method_list:
            qualified_name = f"{model_level.__class__.__qualname__}.{validation_method_name}"
            if hasattr(validation_method, '_is_config_hierarchy_validator'):
                try:
                    validation_method()
                except (ValueError, TypeError, AssertionError) as exc:
                    log.exception(exc)
                    errors.add(f"Failed check {parents}  {qualified_name} with {repr(exc)}")
            elif validation_method_name.startswith('_validate_model_'):
                warnings.warn(
                    f"{qualified_name}"
                    " uses deprecated name based validation function finding. "
                    "Please use @config_hierarchy_validator instead."
                )
                try:
                    validation_method()
                except (ValueError, TypeError, AssertionError) as exc:
                    log.exception(exc)
                    errors.add(f"Failed check {parents}  {qualified_name} with {repr(exc)}")

    def validate_model(self):
        errors = set()
        self.fill_hierarchy(
            model_level=self,
            parents=[],
            errors=errors,
        )
        if len(errors) > 0:
            log = logging.getLogger(__name__)
            log.error(f"{len(errors)} config errors found:")
            for error in errors:
                log.error(error)
            indent = ' ' * 3
            errors_str = f"\n{indent}".join(errors)
            sys.tracebacklimit = 0
            raise ValueError(f"Config Errors (cnt={len(errors)}). Errors=\n{indent}{errors_str}")

    @classmethod
    def _get_config_data_from_loaders(
            cls,
            config_data_loaders: List['BaseConfigDataLoader'],
            config_load_log_level: int = logging.INFO,
            starting_config_data: dict[str, Any] | None = None,
            ignore_file_not_found: bool = False,
    ) -> dict[str, Any]:
        logging.basicConfig(level=config_load_log_level)
        log = logging.getLogger(__name__)

        if starting_config_data is not None:
            config_data = dict(**starting_config_data)
        else:
            config_data = {}

        for loader in config_data_loaders:
            log.debug(f"Loading config with {loader}")
            try:
                loader_config_data = loader.read_config_data(cls)
                merge_configs(config_data, loader_config_data)
            except FileNotFoundError as e:
                if ignore_file_not_found:
                    log.warning(f"{e} with loader {loader}")
                else:
                    raise

        log.debug("Processing Section Inheritance")
        inheritance_errors = process_inheritance(config_data, root_config_data=config_data)
        process_errors_list(
            errors_list=inheritance_errors,
            function_name='Section Inheritance'
        )

        log.debug("Interpolating config value references")
        interpolate_errors = interpolate_values(config_data, root_config_data=config_data)
        process_errors_list(
            errors_list=interpolate_errors,
            function_name='Value Interpolation'
        )
        return config_data

    @classmethod
    def build_config_from_loaders(
            cls,
            config_data_loaders: List['BaseConfigDataLoader'],
            config_load_log_level: int = logging.INFO,
            starting_config_data: dict[str, Any] | None = None,
            ignore_file_not_found: bool = False,
    ) -> Self:
        config_data = cls._get_config_data_from_loaders(
            config_data_loaders=config_data_loaders,
            config_load_log_level=config_load_log_level,
            starting_config_data=starting_config_data,
            ignore_file_not_found=ignore_file_not_found,
        )
        return cls(**config_data)

    @classmethod
    def build_config_from_ini(
            cls,
            file_name: str = 'config.ini',
            start_path: str | Path | None = None,
            config_load_log_level: int = logging.INFO,
            **kwargs: dict[str, Any]
    ) -> Self:
        from config_wrangler.config_data_loaders.ini_config_data_loader import IniConfigDataLoader

        file_loader = IniConfigDataLoader(start_path=start_path, file_name=file_name)
        return cls.build_config_from_loaders(
            config_data_loaders=[file_loader],
            config_load_log_level=config_load_log_level,
            starting_config_data=kwargs,
        )

    @classmethod
    def build_config_from_ini_env(
            cls,
            file_name: str = 'config.ini',
            start_path: str | Path | None = None,
            config_load_log_level: int = logging.INFO,
            **kwargs: dict[str, Any]
    ) -> Self:
        from config_wrangler.config_data_loaders.env_config_data_loader import EnvConfigDataLoader
        from config_wrangler.config_data_loaders.ini_config_data_loader import IniConfigDataLoader

        env_loader = EnvConfigDataLoader()
        file_loader = IniConfigDataLoader(start_path=start_path, file_name=file_name)
        return cls.build_config_from_loaders(
            config_data_loaders=[env_loader, file_loader],
            config_load_log_level=config_load_log_level,
            starting_config_data=kwargs,
        )

    @classmethod
    def build_config_from_toml_env(
            cls,
            file_name: str = 'config.toml',
            start_path: str | Path | None = None,
            config_load_log_level: int = logging.INFO,
            **kwargs: dict[str, Any]
    ) -> Self:
        from config_wrangler.config_data_loaders.env_config_data_loader import EnvConfigDataLoader
        from config_wrangler.config_data_loaders.toml_config_data_loader import TomlConfigDataLoader

        env_loader = EnvConfigDataLoader()
        file_loader = TomlConfigDataLoader(start_path=start_path, file_name=file_name)
        return cls.build_config_from_loaders(
            config_data_loaders=[env_loader, file_loader],
            config_load_log_level=config_load_log_level,
            starting_config_data=kwargs,
        )

    @classmethod
    def build_config_from_yaml_env(
            cls,
            file_name: str = 'config.yaml',
            start_path: str | Path | None = None,
            config_load_log_level: int = logging.INFO,
            **kwargs: dict[str, Any]
    ) -> Self:
        from config_wrangler.config_data_loaders.env_config_data_loader import EnvConfigDataLoader
        from config_wrangler.config_data_loaders.yaml_config_data_loader import YamlConfigDataLoader

        env_loader = EnvConfigDataLoader()
        file_loader = YamlConfigDataLoader(start_path=start_path, file_name=file_name)
        return cls.build_config_from_loaders(
            config_data_loaders=[env_loader, file_loader],
            config_load_log_level=config_load_log_level,
            starting_config_data=kwargs,
        )

    @classmethod
    def build_config_from_many_file_env(
            cls,
            file_base_name: str = 'config',
            start_path: str | Path | None = None,
            config_load_log_level: int = logging.INFO,
            **kwargs: dict[str, Any]
    ) -> Self:
        from config_wrangler.config_data_loaders.env_config_data_loader import EnvConfigDataLoader
        from config_wrangler.config_data_loaders.ini_config_data_loader import IniConfigDataLoader
        from config_wrangler.config_data_loaders.toml_config_data_loader import TomlConfigDataLoader
        from config_wrangler.config_data_loaders.yaml_config_data_loader import YamlConfigDataLoader

        env_loader = EnvConfigDataLoader()

        ini_file_loader = IniConfigDataLoader(start_path=start_path, file_name=f"{file_base_name}.ini")
        toml_file_loader = TomlConfigDataLoader(start_path=start_path, file_name=f"{file_base_name}.toml")
        yaml_file_loader = YamlConfigDataLoader(start_path=start_path, file_name=f"{file_base_name}.yaml")

        return cls.build_config_from_loaders(
            config_data_loaders=[env_loader, ini_file_loader, toml_file_loader, yaml_file_loader],
            config_load_log_level=config_load_log_level,
            starting_config_data=kwargs,
            ignore_file_not_found=True,
        )
