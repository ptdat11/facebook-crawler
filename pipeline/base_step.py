from utils import FormatablePath


class BaseStep:
    def set_path_format(self, **format_kwargs):
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if isinstance(attr, FormatablePath):
                new_formats = dict(**format_kwargs)
                attr.format_kwargs.update(new_formats)
