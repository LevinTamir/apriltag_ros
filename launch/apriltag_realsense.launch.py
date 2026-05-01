"""
Launches:
  1. RealSense D435i (color only)
  2. apriltag_ros detector subscribed to the color stream
  3. pose_printer (prints tag 3D pose continuously)
  4. RViz (preconfigured to show camera image + TF axes)

Launch arguments:
  use_rviz       (bool,  default true) — open RViz
  tag_size_mm    (float, default 64)   — physical AprilTag edge length in mm
                                          (outer black border, edge-to-edge)
"""

from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, DeclareLaunchArgument, OpaqueFunction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def _launch_setup(context, *args, **kwargs):
    pkg_share = FindPackageShare('apriltag_ros')
    config_path = PathJoinSubstitution([pkg_share, 'cfg', 'tags_36h11.yaml'])
    rviz_config = PathJoinSubstitution([pkg_share, 'rviz', 'apriltag.rviz'])

    tag_size_m = float(LaunchConfiguration('tag_size_mm').perform(context)) / 1000.0

    realsense = IncludeLaunchDescription(
        PythonLaunchDescriptionSource([
            FindPackageShare('realsense2_camera'),
            '/launch/rs_launch.py'
        ]),
        launch_arguments={
            'enable_color': 'true',
            'enable_depth': 'false',
            'align_depth.enable': 'false',
            'enable_infra1': 'false',
            'enable_infra2': 'false',
            'rgb_camera.color_profile': '1920x1080x30',
            'pointcloud.enable': 'false',
            'initial_reset': 'false',
        }.items(),
    )

    apriltag = Node(
        package='apriltag_ros',
        executable='apriltag_node',
        name='apriltag',
        parameters=[config_path, {'size': tag_size_m}],
        remappings=[
            ('image_rect', '/camera/camera/color/image_raw'),
            ('camera_info', '/camera/camera/color/camera_info'),
        ],
        output='screen',
    )

    pose_printer = Node(
        package='apriltag_ros',
        executable='pose_printer',
        name='pose_printer',
        parameters=[{
            'camera_frame': 'camera_color_optical_frame',
            'tag_frames': ['tag_20', 'tag_5'],
            'rate_hz': 5.0,
        }],
        output='screen',
    )

    rviz = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', rviz_config],
        condition=IfCondition(LaunchConfiguration('use_rviz')),
    )

    return [realsense, apriltag, pose_printer, rviz]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'use_rviz', default_value='true',
            description='Open RViz on launch',
        ),
        DeclareLaunchArgument(
            'tag_size_mm', default_value='64',
            description='AprilTag edge length in millimeters (outer black border)',
        ),
        OpaqueFunction(function=_launch_setup),
    ])
