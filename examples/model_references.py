import typing

from pydantic import Field

from config_wrangler.config_from_ini_env import ConfigFromIniEnv
from config_wrangler.config_templates.config_hierarchy import ConfigHierarchy
from config_wrangler.config_templates.s3_bucket import S3_Bucket
from config_wrangler.config_types.dynamically_referenced import DynamicallyReferenced


class Bucket_Compare_Section(ConfigHierarchy):
    buckets_to_compare: typing.List[DynamicallyReferenced]
    buckets_to_compare_nl: typing.List[DynamicallyReferenced] = Field(delimiter='\n')
    compare_results_output: str


class BucketCompareConfig(ConfigFromIniEnv):

    class Config:
        validate_all = True
        validate_assignment = True
        allow_mutation = True

    bucket_1: S3_Bucket

    bucket_2: S3_Bucket

    bucket_3: S3_Bucket

    bucket_compare: Bucket_Compare_Section


def main():
    config = BucketCompareConfig(file_name='model_references.ini')

    print(config.bucket_compare.buckets_to_compare)
    for bucket in config.bucket_compare.buckets_to_compare:
        bucket_instance = bucket.get_referenced()
        assert isinstance(bucket_instance, S3_Bucket)
        print(f"{bucket} refers to bucket_instance with bucket_name = {bucket_instance.bucket_name}")
    print()
    print(config.bucket_compare.buckets_to_compare_nl)


if __name__ == '__main__':
    main()
