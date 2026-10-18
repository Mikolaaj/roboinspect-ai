"""Launch the local robot world and one-way Gazebo/ROS bridges."""
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

ROOT = Path(__file__).resolve().parents[2]


def setup(context):
    scenario = LaunchConfiguration('scenario').perform(context)
    if scenario not in ('normal', 'blocked', 'unreachable'):
        raise ValueError('scenario must be normal, blocked or unreachable')
    headless = LaunchConfiguration('headless').perform(context).lower() == 'true'
    engine = LaunchConfiguration('render_engine').perform(context)
    if engine not in ('ogre', 'ogre2'):
        raise ValueError('render_engine must be ogre or ogre2')
    world = ROOT / 'simulation/worlds' / f'hangar_{scenario}_robot.sdf'
    if not world.exists():
        raise FileNotFoundError(f'{world}: run /usr/bin/python3 scripts/build_hangar.py')
    # Server-only mode still uses the desktop display for sensor rendering.
    # EGL headless rendering is not enabled: it crashes in this machine's driver stack.
    flags = '-s ' if headless else ''
    sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(str(Path(get_package_share_directory('ros_gz_sim')) / 'launch/gz_sim.launch.py')),
        launch_arguments={'gz_args': f'-r -v 3 {flags}--render-engine {engine} "{world}"', 'on_exit_shutdown': 'true'}.items(),
    )
    bridge = Node(package='ros_gz_bridge', executable='parameter_bridge', name='roboinspect_bridge',
                  parameters=[{'config_file': str(ROOT / 'config/robot_bridge.yaml')}], output='screen')
    return [sim, bridge]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('scenario', default_value='normal'),
        DeclareLaunchArgument('headless', default_value='false'),
        DeclareLaunchArgument('render_engine', default_value='ogre'),
        OpaqueFunction(function=setup),
    ])
