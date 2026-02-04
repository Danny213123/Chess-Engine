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
        # Set default device
        if self._cuda_available:
            self._device_type = DeviceType.CUDA
            self._num_threads = max(1, multiprocessing.cpu_count() - 1)
            print(f"[V3] CUDA GPU detected, using GPU acceleration + {self._num_threads} CPU threads")
        else:
            self._device_type = DeviceType.CPU
            self._num_threads = max(1, multiprocessing.cpu_count() - 1)
            print(f"[V3] No CUDA GPU, using CPU with {self._num_threads} threads")
    
    def _configure_cuda_environment(self):
        """Try to find and add CUDA paths to environment."""
        cuda_path = os.environ.get('CUDA_PATH')
        
        # If CUDA_PATH not set, try to find it in standard location
        if not cuda_path:
            base_path = r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA"
            if os.path.exists(base_path):
                # Find versions, prefer 12.x over 13.x for numba-cuda compatibility
                all_versions = sorted([d for d in os.listdir(base_path) if d.startswith("v")], reverse=True)
                # Try to find v12.x first (compatible with numba-cuda)
                v12_versions = [v for v in all_versions if v.startswith("v12")]
                versions = v12_versions if v12_versions else all_versions
                if versions:
                    cuda_path = os.path.join(base_path, versions[0])
                    print(f"[V3] Discovered CUDA Path: {cuda_path}")
                    os.environ['CUDA_PATH'] = cuda_path

        if cuda_path:
            # Set CUDA_HOME for numba-cuda
            os.environ['CUDA_HOME'] = cuda_path
            
            # Common subdirectories to add to PATH
            search_paths = [
                os.path.join(cuda_path, 'bin'),
                os.path.join(cuda_path, 'bin', 'x64'), # User specific path
                os.path.join(cuda_path, 'nvvm', 'bin'),
                os.path.join(cuda_path, 'nvvm', 'bin', 'x64'),
                os.path.join(cuda_path, 'lib', 'x64'),
            ]
            
            current_path = os.environ.get('PATH', '')
            updated = False
            for p in search_paths:
                if os.path.exists(p):
                    # Python 3.8+ requires explicit DLL directory addition
                    try:
                        os.add_dll_directory(p)
                    except AttributeError:
                        # Pre-3.8 fallback
                        pass
                    
                    if p not in current_path:
                        os.environ['PATH'] += os.pathsep + p
                        updated = True
            
            if updated:
                print("[V3] Added CUDA paths to environment and DLL search")

            # Set libdevice path for numba-cuda
            libdevice_path = os.path.join(cuda_path, 'nvvm', 'libdevice')
            if os.path.exists(libdevice_path):
                os.environ['NUMBA_CUDA_LIBDEVICE'] = libdevice_path
                os.environ['NUMBAPRO_LIBDEVICE'] = libdevice_path
                print(f"[V3] Set libdevice path: {libdevice_path}")

            # Explicitly find and set NVVM DLL path
            for root, dirs, files in os.walk(os.path.join(cuda_path, 'nvvm')):
                for file in files:
                    if file.startswith("nvvm64") and file.endswith(".dll"):
                        nvvm_path = os.path.join(root, file)
                        os.environ['NUMBAPRO_NVVM'] = nvvm_path
                        print(f"[V3] Set NVVM: {nvvm_path}")
                        break

    def _check_cuda(self) -> bool:
        """Check if CUDA is available via Numba."""
        self._configure_cuda_environment()
        try:
            from numba import cuda
            if cuda.is_available():
                # Get GPU info
                device = cuda.get_current_device()
                # Handle both bytes and str for device name (numba vs numba-cuda)
                name = device.name if isinstance(device.name, str) else device.name.decode()
                print(f"[V3] Found GPU: {name}")
                
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
        # Allow exceeding cpu_count for "Swarm Mode" (IO bound GPU offloading)
        self._num_threads = max(1, num_threads)
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
