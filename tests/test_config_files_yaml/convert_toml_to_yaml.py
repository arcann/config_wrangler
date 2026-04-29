from pathlib import Path
import toml
import yaml


def main():
    test_folder_path = Path(__file__).parents[1]
    toml_folder_path = test_folder_path / 'test_config_files_toml'
    yaml_folder_path = test_folder_path / 'test_config_files_yaml'
    yaml_folder_path.mkdir(exist_ok=True, parents=False)

    for toml_file_path in toml_folder_path.iterdir():
        if toml_file_path.suffix != '.toml':
            continue
        try:
            with toml_file_path.open('rt', encoding='utf-8') as toml_file_stream:
                config_data = toml.load(toml_file_stream)
        except toml.decoder.TomlDecodeError as e:
            print(f"TOML file {toml_file_path}")
            print(f"  ERROR {e}")
        yaml_file = yaml_folder_path / toml_file_path.relative_to(toml_folder_path)
        yaml_file = yaml_file.with_suffix('.yaml')
        with yaml_file.open('w') as yaml_file_stream:
            yaml.dump_safe(config_data, yaml_file_stream, sort_keys=False)
        print(f"Done {toml_file_path} -> {yaml_file}")


if __name__ == '__main__':
    main()
