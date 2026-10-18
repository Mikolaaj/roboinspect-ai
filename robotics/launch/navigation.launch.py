"""Localization and minimal Nav2 stack for a robot freshly spawned at BASE."""
from pathlib import Path
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
ROOT = Path(__file__).resolve().parents[2]

def setup(context):
    scenario = LaunchConfiguration('scenario').perform(context)
    if scenario not in ('normal', 'blocked', 'unreachable'):
        raise ValueError('scenario must be normal, blocked or unreachable')
    map_file = Path(LaunchConfiguration('map').perform(context)).expanduser().resolve()
    if not map_file.is_file():
        raise FileNotFoundError(f'Map not found: {map_file}')
    params = str(ROOT / 'config/nav2.yaml')
    specs = [('nav2_map_server','map_server'),('nav2_amcl','amcl'),
             ('nav2_controller','controller_server'),('nav2_planner','planner_server'),
             ('nav2_smoother','smoother_server'),('nav2_behaviors','behavior_server'),
             ('nav2_bt_navigator','bt_navigator')]
    nodes = []
    for package, name in specs:
        extra = {'use_sim_time':True, 'enable_stamped_cmd_vel':False}
        if name == 'map_server':
            extra['yaml_filename'] = str(map_file)
        nodes.append(Node(package=package, executable=name, name=name, output='screen',
                          parameters=[params, extra],
                          remappings=[('cmd_vel','/roboinspect/cmd_vel')]))
    for child, xyz in [('roboinspect/base_link/lidar', ['0.14','0','0.29']),
                       ('roboinspect/base_link/front_camera', ['0.29','0','0.65'])]:
        nodes.append(Node(package='tf2_ros', executable='static_transform_publisher',
                          arguments=['--x',xyz[0],'--y',xyz[1],'--z',xyz[2],
                                     '--frame-id','base_link','--child-frame-id',child],
                          parameters=[{'use_sim_time':True}]))
    nodes.append(Node(package='nav2_lifecycle_manager', executable='lifecycle_manager',
                      name='lifecycle_manager_navigation', output='screen',
                      parameters=[{'use_sim_time':True,'autostart':True,
                                   'node_names':[name for _,name in specs]}]))
    return nodes

def generate_launch_description():
    return LaunchDescription([DeclareLaunchArgument('scenario',default_value='normal'),
                              DeclareLaunchArgument('map', default_value=[str(ROOT/'maps/hangar_'), LaunchConfiguration('scenario'), '.yaml']),
                              OpaqueFunction(function=setup)])
