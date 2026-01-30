# V3 Device Abstraction Layer
# Handles CUDA GPU / CPU multi-thread selection

import os
from enum import Enum
from typing import Optional
import multiprocessing

class DeviceType(Enum):
    CPU = "cpu"
    CUDA = "cuda"

class Device:
    """Manages compute device selection (CUDA GPU or CPU multi-thread)."""
    
    _instance = None
    _device_type: DeviceType = DeviceType.CPU
    _cuda_available: bool = False
    _num_threads: int = 4
    _vram_limit_mb: int = 512
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Detect available devices and set defaults."""
        # Check for CUDA availability
        self._cuda_available = self._check_cuda()
        
        # Set default device
        if self._cuda_available:
            self._device_type = DeviceType.CUDA
            print(f"[V3] CUDA GPU detected, using GPU acceleration")
        else:
            self._device_type = DeviceType.CPU
            self._num_threads = max(1, multiprocessing.cpu_count() - 1)
            print(f"[V3] No CUDA GPU, using CPU with {self._num_threads} threads")
    
    def _check_cuda(self) -> bool:
        """Check if CUDA is available via Numba."""
        try:
            from numba import cuda
            if cuda.is_available():
                # Get GPU info
                device = cuda.get_current_device()
                print(f"[V3] Found GPU: {device.name.decode()}")
                
                # Check VRAM
                mem_info = cuda.current_context().get_memory_info()
                free_mb = mem_info[0] / (1024 * 1024)
                total_mb = mem_info[1] / (1024 * 1024)
                print(f"[V3] VRAM: {free_mb:.0f}MB free / {total_mb:.0f}MB total")
                
                return True
        except ImportError:
            print("[V3] Numba not installed, falling back to CPU")
        except Exception as e:
            print(f"[V3] CUDA check failed: {e}")
        return False
    
    @property
    def device_type(self) -> DeviceType:
        return self._device_type
    
    @property
    def is_cuda(self) -> bool:
        return self._device_type == DeviceType.CUDA
    
    @property
    def is_cpu(self) -> bool:
        return self._device_type == DeviceType.CPU
    
    @property
    def num_threads(self) -> int:
        return self._num_threads
    
    @property
    def vram_limit_mb(self) -> int:
        return self._vram_limit_mb
    
    def set_device(self, device_type: DeviceType):
        """Manually set device type."""
        if device_type == DeviceType.CUDA and not self._cuda_available:
            raise RuntimeError("CUDA not available on this system")
        self._device_type = device_type
        print(f"[V3] Device set to: {device_type.value}")
    
    def set_threads(self, num_threads: int):
        """Set number of CPU threads for parallel search."""
        self._num_threads = max(1, min(num_threads, multiprocessing.cpu_count()))
        print(f"[V3] CPU threads set to: {self._num_threads}")
    
    def set_vram_limit(self, limit_mb: int):
        """Set VRAM limit for GPU operations."""
        self._vram_limit_mb = max(128, limit_mb)
        print(f"[V3] VRAM limit set to: {self._vram_limit_mb}MB")


# Singleton accessor
_device: Optional[Device] = None

def get_device() -> Device:
    """Get the global device instance."""
    global _device
    if _device is None:
        _device = Device()
    return _device


def force_cpu():
    """Force CPU mode (useful for testing)."""
    get_device().set_device(DeviceType.CPU)


def force_cuda():
    """Force CUDA mode (raises if not available)."""
    get_device().set_device(DeviceType.CUDA)
