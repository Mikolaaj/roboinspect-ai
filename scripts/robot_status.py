#!/usr/bin/python3
"""Check actual ROS sensor messages; optionally save an RGB camera frame as PNG."""
import argparse
import json
import math
from pathlib import Path
import struct
import time
import zlib
import rclpy
from rclpy.qos import qos_profile_sensor_data
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Image, LaserScan


def write_png(path, msg):
    if msg.encoding != 'rgb8':
        raise ValueError(f'Expected rgb8, got {msg.encoding}')
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data) & 0xffffffff)
    raw = b''.join(b'\x00' + bytes(msg.data[y*msg.step:y*msg.step+msg.width*3]) for y in range(msg.height))
    content = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', msg.width, msg.height, 8, 2, 0, 0, 0))
    content += chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout', type=float, default=20)
    parser.add_argument('--image', type=Path)
    args = parser.parse_args()
    rclpy.init()
    node = rclpy.create_node('roboinspect_sensor_check')
    received = {}
    subscriptions = []
    for key, cls, topic in [('odom', Odometry, '/roboinspect/odom'), ('scan', LaserScan, '/roboinspect/scan'), ('image', Image, '/roboinspect/camera/image')]:
        subscriptions.append(node.create_subscription(cls, topic, lambda msg, k=key: received.__setitem__(k, msg), qos_profile_sensor_data))
    try:
        deadline = time.monotonic() + args.timeout
        while len(received) < 3 and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.1)
        result = {'received': sorted(received), 'missing': sorted(set(['odom','scan','image']) - received.keys())}
        if 'odom' in received:
            p = received['odom'].pose.pose.position
            result['odom_xy'] = [p.x, p.y]
            v = received['odom'].twist.twist
            result['velocity'] = {'linear': v.linear.x, 'angular': v.angular.z}
            assert math.isfinite(p.x) and math.isfinite(p.y)
        if 'scan' in received:
            scan = received['scan']
            values = [x for x in scan.ranges if math.isfinite(x) and scan.range_min <= x <= scan.range_max]
            result['lidar_samples'] = len(scan.ranges)
            result['lidar_hits'] = len(values)
            result['nearest_hit_m'] = min(values) if values else None
            assert len(scan.ranges) == 360 and values, 'No valid lidar hits'
        if 'image' in received:
            msg = received['image']
            result['camera'] = {'width': msg.width, 'height': msg.height, 'encoding': msg.encoding, 'bytes': len(msg.data)}
            assert msg.width == 320 and msg.height == 240 and len(msg.data) >= msg.step * msg.height
            if args.image:
                write_png(args.image, msg)
                result['saved_image'] = str(args.image)
        print(json.dumps(result, indent=2))
        return 0 if not result['missing'] else 1
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    raise SystemExit(main())
