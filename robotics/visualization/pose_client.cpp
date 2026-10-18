// Persistent Gazebo transport client for the fixed, collision-free route visuals.
#include <cmath>
#include <iostream>
#include <string>
#include <google/protobuf/text_format.h>
#include <gz/msgs/boolean.pb.h>
#include <gz/msgs/pose_v.pb.h>
#include <gz/transport/Node.hh>

int main() {
  gz::transport::Node node;
  std::string line;
  while (std::getline(std::cin, line)) {
    gz::msgs::Pose_V poses;
    bool valid = line.size() < 100000 && google::protobuf::TextFormat::ParseFromString(line, &poses)
                 && poses.pose_size() <= 161;
    for (const auto &pose : poses.pose()) {
      const auto &p = pose.position();
      const auto &q = pose.orientation();
      const bool name = pose.name() == "route_goal" || pose.name().rfind("route_segment_", 0) == 0;
      valid = valid && name && std::isfinite(p.x()) && std::isfinite(p.y()) && std::isfinite(p.z())
              && std::abs(p.x()) <= 40 && std::abs(p.y()) <= 40 && p.z() >= -3 && p.z() <= .1
              && std::isfinite(q.z()) && std::isfinite(q.w());
    }
    gz::msgs::Boolean reply;
    bool result = false;
    const bool sent = valid && node.Request("/world/roboinspect_hangar/set_pose_vector", poses,
                                          800, reply, result);
    std::cout << (sent && result && reply.data() ? "OK" : "ERROR") << std::endl;
  }
}
