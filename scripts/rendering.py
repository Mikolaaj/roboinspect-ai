"""Process-local graphics policy for Gazebo; never changes system drivers."""
import os
from pathlib import Path
import subprocess

SOFTWARE_KEYS = ['LIBGL_ALWAYS_SOFTWARE','GALLIUM_DRIVER','MESA_LOADER_DRIVER_OVERRIDE',
                 'LIBGL_ALWAYS_INDIRECT','MESA_GL_VERSION_OVERRIDE','MESA_GLSL_VERSION_OVERRIDE',
                 'DRI_PRIME']
OFFLOAD_KEYS = ['__NV_PRIME_RENDER_OFFLOAD','__NV_PRIME_RENDER_OFFLOAD_PROVIDER',
                '__GLX_VENDOR_LIBRARY_NAME','__VK_LAYER_NV_optimus']


def configure(mode=None):
    env = os.environ.copy()
    if mode is None:
        mode = env.get('ROBOINSPECT_RENDERING','auto')
        if 'ROBOINSPECT_RENDERING' not in env and env.get('ROBOINSPECT_SOFTWARE_RENDERING') == '1':
            mode = 'cpu'
    if mode not in ['auto','gpu','cpu']:
        raise ValueError('Rendering must be auto, gpu or cpu')
    requested = mode
    device, driver, reason = None,None,None
    if mode != 'cpu':
        try:
            check = subprocess.run(['nvidia-smi','--query-gpu=name,driver_version','--format=csv,noheader'],
                                   capture_output=True,text=True,timeout=5,check=True)
            device, driver = [s.strip() for s in check.stdout.splitlines()[0].split(',',1)]
            if not Path('/usr/share/glvnd/egl_vendor.d/10_nvidia.json').exists():
                raise RuntimeError('NVIDIA EGL vendor configuration missing')
        except (OSError,subprocess.SubprocessError,IndexError,ValueError,RuntimeError) as exc:
            reason = str(exc)
            if mode == 'gpu':
                raise RuntimeError(f'NVIDIA is unavailable: {reason}. Use --rendering cpu.') from exc
            mode = 'cpu'
        else:
            mode = 'gpu'
    for key in SOFTWARE_KEYS+OFFLOAD_KEYS+['__EGL_VENDOR_LIBRARY_FILENAMES']:
        env.pop(key,None)
    if mode == 'gpu':
        env.update(__NV_PRIME_RENDER_OFFLOAD='1',__GLX_VENDOR_LIBRARY_NAME='nvidia',
                   __VK_LAYER_NV_optimus='NVIDIA_only',
                   __EGL_VENDOR_LIBRARY_FILENAMES='/usr/share/glvnd/egl_vendor.d/10_nvidia.json')
    else:
        device, driver = 'Mesa llvmpipe (CPU)',None
        env.update(LIBGL_ALWAYS_SOFTWARE='1',GALLIUM_DRIVER='llvmpipe',
                   MESA_LOADER_DRIVER_OVERRIDE='llvmpipe',__GLX_VENDOR_LIBRARY_NAME='mesa',
                   __EGL_VENDOR_LIBRARY_FILENAMES='/usr/share/glvnd/egl_vendor.d/50_mesa.json')
    env.update(ROBOINSPECT_RENDERING=mode,ROBOINSPECT_RENDER_DEVICE=device)
    return env, {'requested':requested,'mode':mode,'device':device,'driver':driver,'fallback_reason':reason}
