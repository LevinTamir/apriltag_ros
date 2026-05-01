#!/usr/bin/env python3
"""
Subscribes to the tf tree and prints the pose of each configured AprilTag
(camera_color_optical_frame -> <tag_frame>) at a fixed rate.

Parameters:
  camera_frame  (string)        — TF parent frame
  tag_frames    (string array)  — list of TF child frames to look up
  rate_hz       (double)        — print rate
  ema_alpha     (double)        — exponential moving average factor (per tag)
"""

import math
import rclpy
from rclpy.node import Node
import tf2_ros
from tf2_ros import LookupException, ConnectivityException, ExtrapolationException


class PosePrinter(Node):
    def __init__(self):
        super().__init__('pose_printer')
        self.declare_parameter('camera_frame', 'camera_color_optical_frame')
        self.declare_parameter('tag_frames', ['tag_20', 'tag_5'])
        self.declare_parameter('rate_hz', 5.0)
        self.declare_parameter('ema_alpha', 0.3)

        self.camera_frame = self.get_parameter('camera_frame').value
        self.tag_frames = list(self.get_parameter('tag_frames').value)
        rate = self.get_parameter('rate_hz').value
        self.alpha = self.get_parameter('ema_alpha').value

        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        self.timer = self.create_timer(1.0 / rate, self._tick)
        self.smooth_xyz = {f: None for f in self.tag_frames}
        self.ever_seen = {f: False for f in self.tag_frames}

        self.get_logger().info(
            f'Looking up TF: {self.camera_frame} -> {self.tag_frames} at {rate} Hz'
        )

    def _tick(self):
        for frame in self.tag_frames:
            try:
                tf = self.tf_buffer.lookup_transform(
                    self.camera_frame, frame, rclpy.time.Time()
                )
            except (LookupException, ConnectivityException, ExtrapolationException):
                if not self.ever_seen[frame]:
                    self.get_logger().warn(
                        f'No transform yet from {self.camera_frame} to {frame}',
                        throttle_duration_sec=2.0,
                    )
                continue

            t = tf.transform.translation
            raw = (t.x, t.y, t.z)

            a = self.alpha
            if self.smooth_xyz[frame] is None:
                self.smooth_xyz[frame] = raw
            else:
                prev = self.smooth_xyz[frame]
                self.smooth_xyz[frame] = tuple(
                    a * r + (1 - a) * s for r, s in zip(raw, prev)
                )

            sx, sy, sz = self.smooth_xyz[frame]
            distance = math.sqrt(sx ** 2 + sy ** 2 + sz ** 2)

            self.get_logger().info(
                f'{frame}: xyz=({sx:+.4f}, {sy:+.4f}, {sz:+.4f}) m  '
                f'dist={distance:.4f} m'
            )
            self.ever_seen[frame] = True

    @staticmethod
    def _quat_to_rpy(x, y, z, w):
        sinr_cosp = 2 * (w * x + y * z)
        cosr_cosp = 1 - 2 * (x * x + y * y)
        roll = math.atan2(sinr_cosp, cosr_cosp)

        sinp = 2 * (w * y - z * x)
        pitch = math.copysign(math.pi / 2, sinp) if abs(sinp) >= 1 else math.asin(sinp)

        siny_cosp = 2 * (w * z + x * y)
        cosy_cosp = 1 - 2 * (y * y + z * z)
        yaw = math.atan2(siny_cosp, cosy_cosp)
        return roll, pitch, yaw


def main():
    rclpy.init()
    node = PosePrinter()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
