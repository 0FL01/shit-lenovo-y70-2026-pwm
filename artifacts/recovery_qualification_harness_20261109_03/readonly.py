"""Ordinary public API boundary, not a hostile Python reflection sandbox."""
from copy import deepcopy
class ReadOnly:
    _references = frozenset()
    _snapshots = frozenset()
    def __setattr__(self, name, value):
        if not name.startswith('_'):
            raise AttributeError('public state is read-only: '+name)
        object.__setattr__(self,name,value)
    def __getattr__(self,name):
        if name not in self._snapshots and name not in self._references: raise AttributeError(name)
        try: value=object.__getattribute__(self,'_'+name)
        except AttributeError: raise AttributeError(name) from None
        return value if name in self._references else deepcopy(value)
    def __delattr__(self,name):
        if not name.startswith('_'): raise AttributeError('public state is read-only')
        object.__delattr__(self,name)
    def _initialize_once(self):
        if getattr(self,'_initialized',False): raise ValueError('object cannot be reinitialized')
        self._initialized=True
