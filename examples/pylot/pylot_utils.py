import cv2
from erdos.data_stream import DataStream


# Sensor streams
def is_camera_stream(stream):
    return (stream.get_label('sensor_type') == 'camera' and
            stream.get_label('camera_type') == 'SceneFinal')


def is_depth_camera_stream(stream):
    return (stream.get_label('sensor_type') == 'camera' and
            stream.get_label('camera_type') == 'Depth')


def is_lidar_stream(stream):
    return stream.get_label('sensor_type') == 'lidar'


# Ground streams
def is_ground_segmented_camera_stream(stream):
    return (stream.get_label('sensor_type') == 'camera' and
            stream.get_label('camera_type') == 'SemanticSegmentation')


def is_ground_pedestrians_stream(stream):
    return stream.name == 'pedestrians'


def is_ground_vehicles_stream(stream):
    return stream.name == 'vehicles'


def is_ground_traffic_lights_stream(stream):
    return stream.name == 'traffic_lights'


def is_ground_traffic_signs_stream(stream):
    return stream.name == 'traffic_signs'


def is_ground_vehicle_pos_stream(stream):
    return stream.name == 'vehicle_pos'


def is_world_transform_stream(stream):
    return stream.name == 'world_transform'


def is_ground_acceleration_stream(stream):
    return stream.name == 'acceleration'


def is_ground_forward_speed_stream(stream):
    return stream.name == 'forward_speed'


# ERDOS streams
def create_segmented_camera_stream(name):
    return DataStream(name=name,
                      labels={'segmented': 'true'})


def is_segmented_camera_stream(stream):
    return stream.get_label('segmented') == 'true'


def create_obstacles_stream(name):
    return DataStream(name=name, labels={'obstacles': 'true'})


def is_obstacles_stream(stream):
    return stream.get_label('obstacles') == 'true'


def create_traffic_lights_stream(name):
    return DataStream(name=name, labels={'traffic_lights': 'true'})


def is_traffic_lights_stream(stream):
    return stream.get_label('traffic_lights') == 'true'


def create_fusion_stream(name):
    return DataStream(name=name, labels={'fusion_output': 'true'})


def is_fusion_stream(stream):
    return stream.get_label('fusion_output') == 'true'


def create_agent_action_stream():
    # XXX(ionel): HACK! We set no_watermark to avoid closing the cycle in
    # the data-flow.
    return DataStream(name='action_stream',
                      labels={'no_watermark': 'true'})


def create_waypoints_stream():
    return DataStream(name='waypoints')


def is_waypoints_stream(stream):
    return stream.name == 'waypoints'


def create_detected_lane_stream(name):
    return DataStream(name=name,
                      labels={'detected_lanes': 'true'})


def is_detected_lane_stream(stream):
    return stream.get_label('detected_lanes') == 'true'


def add_timestamp(timestamp, image_np):
    txt_font = cv2.FONT_HERSHEY_SIMPLEX
    timestamp_txt = '{}'.format(timestamp)
    # Put timestamp text.
    cv2.putText(image_np, timestamp_txt, (5, 15), txt_font, 0.5,
                (0, 0, 0), thickness=1, lineType=cv2.LINE_AA)


def bgra_to_bgr(image_np):
    return image_np[:, :, :3]


def bgra_to_rgb(image_np):
    image_np = image_np[:, :, :3]
    image_np = image_np[:, :, ::-1]


def bgr_to_rgb(image_np):
    return image_np[:, :, ::-1]


def rgb_to_bgr(image_np):
    return image_np[:, :, ::-1]
