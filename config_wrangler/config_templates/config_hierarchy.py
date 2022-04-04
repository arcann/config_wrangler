from pydantic import PrivateAttr, BaseModel


class ConfigHierarchy(BaseModel):
    _root_config = PrivateAttr()
    _parents = PrivateAttr()

    def full_item_name(self, item_name: str = None, delimiter: str = ' -> '):
        try:
            if item_name is None:
                return delimiter.join(self._parents)
            else:
                return delimiter.join(self._parents + item_name)
        except AttributeError as e:
            raise AttributeError(f"{e} not found in {repr(self)}")
