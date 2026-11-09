"""Inactive fixed-stat bridge, not a full ProcFS replacement or loader install.
Exact frozen reader module must be explicitly loaded before this module.
"""
from identity_bound_reader_revision03 import Held

class StatShim:
    __slots__=('_held','_dep','_terminal','_invoke')
    @property
    def terminal(self):return self._terminal
    @property
    def held(self):return self._held
    def __init__(self,*,held,dependency):
        if hasattr(self,'_held'):raise ValueError('Cannot reset shim')
        if type(held) is not Held:raise TypeError('Exact reviewed Held required')
        self._held=held;self._dep=dependency;self._terminal=False
        # Reuse ACTUAL committed sanitizer; no emulated decorator behavior.
        self._invoke=dependency.safe_errors('proc_read_failed')(self._read)
    def _cleanup(self):
        try:self._held.close()
        except BaseException:pass # Original failure retained; reader logs close uncertainty.
    def _read(self,path,cap,deadline):
        try:
            if self._terminal or self._held.terminal or self._held.closed:raise self._dep.ProbeError('Bound reader already terminal',trust_invalidated=True)
            if type(path) is not str or path!='/proc/'+str(self._held.pid)+'/stat' or type(cap) is not int or cap!=16384:
                raise ValueError('Only exact planned stat request/cap supported')
            return self._held.read_stat(deadline=deadline)
        except (KeyboardInterrupt,SystemExit):
            self._terminal=True;self._cleanup();raise
        except BaseException as error:
            self._terminal=True;self._cleanup()
            if isinstance(error,self._dep.ProbeError) and error.trust_invalidated:raise
            raise self._dep.ProbeError('Bound reader terminal',trust_invalidated=True,code='bound_reader_terminal') from error
    def read(self,path,cap,deadline):return self._invoke(path,cap,deadline)

def association_type(dependency):
    """Inactive subclass: actual association body/sanitizer unchanged.
    Original interrupts propagate, but cannot leave this composition reusable.
    """
    class InterruptStickyAssociation(dependency.LinuxAssociation):
        def __call__(self,deadline):
            try:return super().__call__(deadline)
            except (KeyboardInterrupt,SystemExit):
                self.trust_invalidated=True
                raise
    return InterruptStickyAssociation
