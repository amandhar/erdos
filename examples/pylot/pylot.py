from absl import app
from absl import flags

import config
from ground_agent_operator import GroundAgentOperator
from erdos_agent_operator import ERDOSAgentOperator
from camera_replay_operator import CameraReplayOperator
from carla_operator import CarlaOperator
from control_operator import ControlOperator
from detection_operator import DetectionOperator
try:
    from detection_center_net_operator import DetectionCenterNetOperator
except ImportError:
    print("Error importing CenterNet detector.")
from fusion_operator import FusionOperator
from fusion_verification_operator import FusionVerificationOperator
from lane_detection_operator import LaneDetectionOperator
from lidar_visualizer_operator import LidarVisualizerOperator
from obstacle_accuracy_operator import ObstacleAccuracyOperator
from object_tracker_operator import ObjectTrackerOp
from planner.planner_operator import PlannerOperator
from segmentation_drn_operator import SegmentationDRNOperator
try:
    from segmentation_dla_operator import SegmentationDLAOperator
except ImportError:
    print("Error importing DLA segmentation.")
from segmentation_eval_operator import SegmentationEvalOperator
from segmentation_eval_ground_operator import SegmentationEvalGroundOperator
from detection_eval_ground_operator import DetectionEvalGroundOperator
from segmented_video_operator import SegmentedVideoOperator
from traffic_light_det_operator import TrafficLightDetOperator
from video_operator import VideoOperator
from waypointer_operator import WaypointerOperator

import erdos.graph
from erdos.operators import RecordOp
from erdos.operators import ReplayOp

FLAGS = flags.FLAGS
RGB_CAMERA_NAME = 'front_rgb_camera'
DEPTH_CAMERA_NAME = 'front_depth_camera'
SEGMENTED_CAMERA_NAME = 'front_semantic_camera'


def add_camera_replay_ops(graph):
    camera_ops = []
    for i in range(0, FLAGS.num_cameras, 1):
        op_name = 'camera{}'.format(i)
        camera_op = graph.add(
            CameraReplayOperator,
            name=op_name,
            init_args={'log_file_name': FLAGS.log_file_name},
            setup_args={'op_name': op_name})
        camera_ops.append(camera_op)
    # replay_rgb_op = ReplayOp('pylot_rgb_camera_data.erdos',
    #                          frequency=10,
    #                          name='replay_rgb_camera')
    # camera_streams = replay_rgb_op([])
    return camera_ops


def add_carla_op(graph, camera_setups):
    carla_op = graph.add(
        CarlaOperator,
        name='carla',
        init_args={
            'flags': FLAGS,
            'camera_setups': camera_setups,
            'lidar_stream_names': [],
            'log_file_name': FLAGS.log_file_name,
            'csv_file_name': FLAGS.csv_log_file_name
        },
        setup_args={
            'camera_setups': camera_setups,
            'lidar_stream_names': []
        })
    return carla_op


def add_ground_agent_op(graph, carla_op):
    agent_op = graph.add(
        GroundAgentOperator,
        name='ground_agent',
        # TODO(ionel): Do not hardcode city name!
        init_args={
            'city_name': 'Town01',
            'flags': FLAGS,
            'log_file_name': FLAGS.log_file_name,
            'csv_file_name': FLAGS.csv_log_file_name
        })
    graph.connect([carla_op], [agent_op])
    graph.connect([agent_op], [carla_op])
    return agent_op


def add_erdos_agent_op(graph,
                       carla_op,
                       depth_camera_name,
                       segmentation_ops,
                       obj_detector_ops,
                       traffic_light_det_ops,
                       lane_detection_ops):
    agent_op = graph.add(
        ERDOSAgentOperator,
        name='erdos_agent',
        init_args={
            # TODO(ionel): Do not hardcode city name!
            'city_name': 'Town01',
            'depth_camera_name': depth_camera_name,
            'flags': FLAGS,
            'log_file_name': FLAGS.log_file_name,
            'csv_file_name': FLAGS.csv_log_file_name
        },
        setup_args={'depth_camera_name': depth_camera_name})
    input_ops = [carla_op] + traffic_light_det_ops + obj_detector_ops +\
                segmentation_ops + lane_detection_ops
    graph.connect(input_ops, [agent_op])
    graph.connect([agent_op], [carla_op])
    return agent_op


def add_waypointer_op(graph,
                      carla_op,
                      agent_op,
                      goal_location,
                      goal_orientation):
    waypointer_op = graph.add(
        WaypointerOperator,
        name='waypointer',
        init_args={
            'city_name': 'Town01',
            'goal_location': goal_location,
            'goal_orientation': goal_orientation,
            'flags': FLAGS,
            'log_file_name': FLAGS.log_file_name,
            'csv_file_name': FLAGS.csv_log_file_name
        })
    graph.connect([carla_op], [waypointer_op])
    graph.connect([waypointer_op], [agent_op])
    return agent_op


def add_lidar_visualizer_op(graph, carla_op):
    lidar_visualizer_op = graph.add(
        LidarVisualizerOperator,
        name='lidar_visualizer',
        init_args={'flags': FLAGS,
                   'log_file_name': FLAGS.log_file_name})
    graph.connect([carla_op], [lidar_visualizer_op])


def add_lidar_record_op(graph, carla_op):
    record_lidar_op = graph.add(
        RecordOp,
        name='record_lidar',
        init_args={'filename': 'pylot_lidar_data.erdos'},
        setup_args={'filter': 'lidar'})
    graph.connect([carla_op], [record_lidar_op])
    return record_lidar_op


def add_camera_video_op(graph, carla_op, name, filter_name):
    video_op = graph.add(
        VideoOperator,
        name=name,
        init_args={'flags': FLAGS,
                   'log_file_name': FLAGS.log_file_name},
        setup_args={'filter_name': filter_name})
    graph.connect([carla_op], [video_op])
    return video_op


def add_segmented_video_op(graph, carla_op):
    segmented_video_op = graph.add(
        SegmentedVideoOperator,
        name='segmented_video',
        init_args={'flags': FLAGS,
                   'log_file_name': FLAGS.log_file_name})
    graph.connect([carla_op], [segmented_video_op])
    return segmented_video_op


def add_record_op(graph, carla_op, name, filename, filter_name):
    record_op = graph.add(
        RecordOp,
        name=name,
        init_args={'filename': filename},
        setup_args={'filter_name': filter_name})
    graph.connect([carla_op], [record_op])
    return record_op


def add_record_carla_op(graph, carla_op):
    input_names = [
        'vehicle_pos', 'acceleration', 'forward_speed',
        'traffic_lights', 'pedestrians', 'vehicles', 'traffic_signs'
    ]
    record_carla_op = graph.add(
        RecordOp,
        name='record_carla',
        init_args={'filename': 'pylot_carla_data.erdos'},
        setup_args={'filter': input_names})
    graph.connect([carla_op], [record_carla_op])


def add_detector_op_helper(graph, name, model_path, gpu_memory_fraction):
    obj_detector_op = graph.add(
        DetectionOperator,
        name=name,
        setup_args={'output_stream_name': 'obj_stream'},
        init_args={'output_stream_name': 'obj_stream',
                   'model_path': model_path,
                   'flags': FLAGS,
                   'log_file_name': FLAGS.log_file_name,
                   'csv_file_name': FLAGS.csv_log_file_name},
        _resources = {"GPU": gpu_memory_fraction})
    return obj_detector_op


def add_detector_ops(graph, carla_op):
    detector_ops = []
    if FLAGS.detector_ssd_mobilenet_v1:
        detector_ops.append(add_detector_op_helper(
            graph,
            'detector_ssd_mobilenet_v1',
            'dependencies/data/ssd_mobilenet_v1_coco_2018_01_28/frozen_inference_graph.pb',
            FLAGS.obj_detection_gpu_memory_fraction))
    if FLAGS.detector_frcnn_resnet101:
        detector_ops.append(add_detector_op_helper(
            graph,
            'detector_faster_rcnn_resnet101',
            'dependencies/data/faster_rcnn_resnet101_coco_2018_01_28/frozen_inference_graph.pb',
            FLAGS.obj_detection_gpu_memory_fraction))
    if FLAGS.detector_ssd_resnet50_v1:
        detector_ops.append(add_detector_op_helper(
            graph,
            'detector_ssd_resnet50_v1',
            'dependencies/data/ssd_resnet50_v1_fpn_shared_box_predictor_640x640_coco14_sync_2018_07_03/frozen_inference_graph.pb',
            FLAGS.obj_detection_gpu_memory_fraction))
    if FLAGS.detector_center_net:
        obj_det_op = graph.add(
            DetectionCenterNetOperator,
            name='detector_center_net',
            setup_args={'output_stream_name': 'obj_stream'},
            init_args={'output_stream_name': 'obj_stream',
                       'flags': FLAGS,
                       'log_file_name': FLAGS.log_file_name,
                       'csv_file_name': FLAGS.csv_log_file_name})
        detector_ops.append(obj_det_op)
    graph.connect([carla_op], detector_ops)
    return detector_ops


def add_traffic_light_op(graph, carla_op):
    traffic_light_det_op = graph.add(
        TrafficLightDetOperator,
        name='traffic_light_detector',
        setup_args={'output_stream_name': 'detected_traffic_lights'},
        init_args={'output_stream_name': 'detected_traffic_lights',
                   'flags': FLAGS,
                   'log_file_name': FLAGS.log_file_name,
                   'csv_file_name': FLAGS.csv_log_file_name},
        _resources = {"GPU": FLAGS.traffic_light_det_gpu_memory_fraction})
    graph.connect([carla_op], [traffic_light_det_op])
    return traffic_light_det_op


def add_object_tracking_op(graph, carla_op, obj_detector_ops):
    tracker_op = None
    name = 'tracker_' + FLAGS.tracker_type
    setup_args = {'output_stream_name': 'tracker_stream'}
    init_args = {'output_stream_name': 'tracker_stream',
                 'tracker_type': FLAGS.tracker_type,
                 'flags': FLAGS,
                 'log_file_name': FLAGS.log_file_name,
                 'csv_file_name': FLAGS.csv_log_file_name}
    if FLAGS.tracker_type == 'cv2':
        # Doesn't require a GPU.
        tracker_op = graph.add(
            ObjectTrackerOp,
            name=name,
            setup_args=setup_args,
            init_args=init_args)
    else:
        # Other trackers require a GPU.
        tracker_op = graph.add(
            ObjectTrackerOp,
            name=name,
            setup_args=setup_args,
            init_args=init_args,
            _resources = {"GPU": FLAGS.obj_tracking_gpu_memory_fraction})
    graph.connect([carla_op] + obj_detector_ops, [tracker_op])
    return tracker_op


def add_obstacle_accuracy_op(graph,
                             obj_detector_ops,
                             carla_op,
                             rgb_camera_setup,
                             depth_camera_name):
    obstacle_accuracy_op = graph.add(
        ObstacleAccuracyOperator,
        name='obstacle_accuracy',
        setup_args={'depth_camera_name': depth_camera_name},
        init_args={'rgb_camera_setup': rgb_camera_setup,
                   'flags': FLAGS,
                   'log_file_name': FLAGS.log_file_name,
                   'csv_file_name': FLAGS.csv_log_file_name})
    graph.connect(obj_detector_ops + [carla_op],
                  [obstacle_accuracy_op])
    return obstacle_accuracy_op


def add_segmentation_drn_op(graph, carla_op):
    segmentation_op = graph.add(
        SegmentationDRNOperator,
        name='segmentation_drn',
        setup_args={'output_stream_name': 'segmented_stream'},
        init_args={'output_stream_name': 'segmented_stream',
                   'flags': FLAGS,
                   'log_file_name': FLAGS.log_file_name,
                   'csv_file_name': FLAGS.csv_log_file_name},
        _resources = {"GPU": FLAGS.segmentation_drn_gpu_memory_fraction})
    graph.connect([carla_op], [segmentation_op])
    return segmentation_op


def add_segmentation_dla_op(graph, carla_op):
    segmentation_op = graph.add(
        SegmentationDLAOperator,
        name='segmentation_dla',
        setup_args={'output_stream_name': 'segmented_stream'},
        init_args={'output_stream_name': 'segmented_stream',
                   'flags': FLAGS,
                   'log_file_name': FLAGS.log_file_name,
                   'csv_file_name': FLAGS.csv_log_file_name},
        _resources = {"GPU": FLAGS.segmentation_dla_gpu_memory_fraction})
    graph.connect([carla_op], [segmentation_op])
    return segmentation_op


def add_segmentation_eval_op(graph, carla_op, segmentation_op,
                             ground_stream_name, segmented_stream_name):
    segmentation_eval_op = graph.add(
        SegmentationEvalOperator,
        name='segmentation_eval',
        init_args={'flags': FLAGS,
                   'log_file_name': FLAGS.log_file_name,
                   'csv_file_name': FLAGS.csv_log_file_name},
        setup_args={'ground_stream_name': ground_stream_name,
                    'segmented_stream_name': segmented_stream_name})
    graph.connect([carla_op, segmentation_op], [segmentation_eval_op])
    return segmentation_eval_op


def add_lane_detection_op(graph, carla_op):
    lane_det_op = graph.add(
        LaneDetectionOperator,
        name='lane_detection',
        init_args={'output_stream_name': 'lane_det',
                   'flags': FLAGS,
                   'log_file_name': FLAGS.log_file_name,
                   'csv_file_name': FLAGS.csv_log_file_name},
        setup_args={'output_stream_name': 'lane_det'})
    graph.connect([carla_op], [lane_det_op])
    return lane_det_op


def add_segmentation_ground_eval_op(graph, carla_op, ground_stream_name):
    seg_eval_op = graph.add(
        SegmentationEvalGroundOperator,
        name='segmentation_ground_eval',
        init_args={'flags': FLAGS,
                   'log_file_name': FLAGS.log_file_name,
                   'csv_file_name': FLAGS.csv_log_file_name},
        setup_args={'ground_stream_name': ground_stream_name})
    graph.connect([carla_op], [seg_eval_op])
    return seg_eval_op


def add_fusion_ops(graph, carla_op, obj_detector_ops):
    fusion_op = graph.add(
        FusionOperator,
        name='fusion',
        setup_args={'output_stream_name': 'fusion_vehicles'},
        init_args={'flags': FLAGS,
                   'output_stream_name': 'fusion_vehicles',
                   'log_file_name': FLAGS.log_file_name,
                   'csv_file_name': FLAGS.csv_log_file_name})
    fusion_verification_op = graph.add(
        FusionVerificationOperator,
        name='fusion_verifier',
        init_args={'log_file_name': FLAGS.log_file_name})
    graph.connect(obj_detector_ops + [carla_op], [fusion_op])
    graph.connect([fusion_op, carla_op], [fusion_verification_op])
    return (fusion_op, fusion_verification_op)


def add_eval_ground_truth_detector_op(graph,
                                      carla_op,
                                      rgb_camera_setup,
                                      depth_camera_name):
    ground_truth_op = graph.add(
        DetectionEvalGroundOperator,
        name='eval_ground_detection',
        setup_args={'depth_camera_name': depth_camera_name},
        init_args={
            'rgb_camera_setup': rgb_camera_setup,
            'flags': FLAGS,
            'log_file_name': FLAGS.log_file_name,
            'csv_file_name': FLAGS.csv_log_file_name
        },
    )
    graph.connect([carla_op], [ground_truth_op])
    return ground_truth_op


def add_visualization_operators(graph, carla_op):
    if FLAGS.visualize_rgb_camera:
        camera_video_op = add_camera_video_op(graph,
                                              carla_op,
                                              'rgb_camera',
                                              RGB_CAMERA_NAME)

    if FLAGS.visualize_depth_camera:
        depth_video_op = add_camera_video_op(graph,
                                             carla_op,
                                             'depth_camera_video',
                                             DEPTH_CAMERA_NAME)

    if FLAGS.visualize_lidar:
        lidar_visualizer_op = add_lidar_visualizer_ops(graph, carla_op)

    if FLAGS.visualize_segmentation:
        # Segmented camera. The stream comes from CARLA.
        segmented_video_op = add_segmented_video_op(graph, carla_op)


def add_recording_operators(graph, carla_op):
    if FLAGS.record_rgb_camera:
        record_rgb_op = add_record_op(graph,
                                      carla_op,
                                      'record_rgb_camera',
                                      'pylot_rgb_camera_data.erdos',
                                      RGB_CAMERA_NAME)

    if FLAGS.record_depth_camera:
        record_depth_camera_op = add_record_op(
            graph,
            'record_depth_camera',
            'pylot_depth_camera_data.erdos',
            DEPTH_CAMERA_NAME)

    if FLAGS.record_lidar:
        record_lidar_op = add_lidar_record_op(graph, carla_op)

    if FLAGS.record_ground_truth:
        record_carla_op = add_record_carla_op(graph, carla_op)


def main(argv):

    # Define graph
    graph = erdos.graph.get_current_graph()

    rgb_camera_setup = (RGB_CAMERA_NAME,
                        'SceneFinal',
                        (FLAGS.carla_camera_image_width,
                         FLAGS.carla_camera_image_height),
                        (2.0, 0.0, 1.4))
    camera_setups = [rgb_camera_setup,
                     (DEPTH_CAMERA_NAME, 'Depth',
                      (FLAGS.carla_camera_image_width,
                       FLAGS.carla_camera_image_height),
                      (2.0, 0.0, 1.4)),
                     (SEGMENTED_CAMERA_NAME, 'SemanticSegmentation',
                      (FLAGS.carla_camera_image_width,
                       FLAGS.carla_camera_image_height),
                      (2.0, 0.0, 1.4))]

    # Add operators to the graph.
    carla_op = add_carla_op(graph, camera_setups)

    # Add visual operators.
    add_visualization_operators(graph, carla_op)

    # Add recording operators.
    add_recording_operators(graph, carla_op)

    # XXX(ionel): This planner is not currently in use.
    # planner_op = PlannerOperator('Town01', goal_location, goal_orientation)
    # planner_streams = planner_op([carla_op.get_output_stream('vehicle_pos')])
    # control_streams = control_op(planner_streams)

    segmentation_ops = []
    if FLAGS.segmentation_drn:
        segmentation_op = add_segmentation_drn_op(graph, carla_op)
        segmentation_ops.append(segmentation_op)
        if FLAGS.evaluate_segmentation:
            eval_segmentation_op = add_segmentation_eval_op(
                graph, carla_op, segmentation_op,
                SEGMENTED_CAMERA_NAME, 'segmented_stream')

    if FLAGS.segmentation_dla:
        segmentation_op = add_segmentation_dla_op(graph, carla_op)
        segmentation_ops.append(segmentation_op)
        if FLAGS.evaluate_segmentation:
            eval_segmentation_op = add_segmentation_eval_op(
                graph, carla_op, segmentation_op,
                SEGMENTED_CAMERA_NAME, 'segmented_stream')

    if FLAGS.eval_ground_truth_segmentation:
        eval_ground_truth_segmentation_op = add_segmentation_ground_eval_op(
            graph, carla_op, SEGMENTED_CAMERA_NAME)

    # This operator evaluates the temporal decay of the ground truth of
    # object detection across timestamps.
    if FLAGS.eval_ground_truth_object_detection:
        eval_ground_truth_detector_op = add_eval_ground_truth_detector_op(
            graph, carla_op, rgb_camera_setup, DEPTH_CAMERA_NAME)

    obj_detector_ops = []
    if FLAGS.obj_detection:
        obj_detector_ops = add_detector_ops(graph, carla_op)

        if FLAGS.evaluate_obj_detection:
            obstacle_accuracy_op = add_obstacle_accuracy_op(graph,
                                                            obj_detector_ops,
                                                            carla_op,
                                                            rgb_camera_setup,
                                                            DEPTH_CAMERA_NAME)

        if FLAGS.obj_tracking:
            tracker_op = add_object_tracking_op(graph, carla_op, obj_detector_ops)

        if FLAGS.fusion:
            (fusion_op, fusion_verification_op) = add_fusion_ops(graph,
                                                                 carla_op,
                                                                 obj_detector_ops)

    traffic_light_det_ops = []
    if FLAGS.traffic_light_det:
        traffic_light_det_ops.append(add_traffic_light_op(graph, carla_op))

    lane_detection_ops = []
    if FLAGS.lane_detection:
        lane_detection_ops.append(add_lane_detection_op(graph, carla_op))

    agent_op = None
    if FLAGS.ground_agent_operator:
        agent_op = add_ground_agent_op(graph, carla_op)
    else:
        # TODO(ionel): The ERDOS agent doesn't use obj tracker and fusion.
        agent_op = add_erdos_agent_op(graph,
                                      carla_op,
                                      DEPTH_CAMERA_NAME,
                                      segmentation_ops,
                                      obj_detector_ops,
                                      traffic_light_det_ops,
                                      lane_detection_ops)

    goal_location = (234.269989014, 59.3300170898, 39.4306259155)
    goal_orientation = (1.0, 0.0, 0.22)
    waypointer_op = add_waypointer_op(graph,
                                      carla_op,
                                      agent_op,
                                      goal_location,
                                      goal_orientation)

    graph.execute(FLAGS.framework)


if __name__ == '__main__':
    app.run(main)
