

class BrowsableJSONViewMixin:
    serializer_class = None

    def get_serializer(self, *args, **kwargs):
        if self.serializer_class is None:
            return None
        return self.serializer_class(*args, **kwargs)