from cv_bridge import CvBridge

from erdos.logging_op import LoggingOp
from erdos.data_stream import DataStream
from erdos.message import Message
from erdos.utils import setup_logging
import pylot_utils


class DetectionOperator(LoggingOp):
    def __init__(self,
                 name,
                 min_runtime_us=None,
                 max_runtime_us=None,
                 min_det_objs=3,
                 max_det_objs=15,
                 buffer_logs=False):
        super(DetectionOperator, self).__init__(name, buffer_logs)
        self._logger = setup_logging(self.name, 'pylot.log')
        self._min_runtime = min_runtime_us
        self._max_runtime = max_runtime_us
        self._min_det_objs = min_det_objs
        self._max_det_objs = max_det_objs
        self._bridge = CvBridge()
        self._cnt = 0

    @staticmethod
    def setup_streams(input_streams, op_name):
        def is_rgb_camera_stream(stream):
            return stream.labels.get('camera_type', '') == 'RGB'

        input_streams.filter(is_rgb_camera_stream)\
            .add_callback(DetectionOperator.on_msg_camera_stream)
        # TODO(ionel): Specify output stream type
        return [
            DataStream(
                name='{}_output'.format(op_name),
                labels={
                    'detector': 'true',
                    'type': 'bbox'
                })
        ]

    def on_msg_camera_stream(self, msg):
        cv_img = self._bridge.imgmsg_to_cv2(msg.data, "bgr8")
        if self._cnt % 10 == 0:
            # TODO(ionel): We receive all frames, but only run detection once
            # every 10 frames. We shouldn't receive all frames.
            pylot_utils.do_work(self._logger, self._min_runtime,
                                self._max_runtime)
            bboxes = pylot_utils.generate_synthetic_bounding_boxes(
                self._min_det_objs, self._max_det_objs)
            output_msg = Message(bboxes, msg.timestamp)
            output_name = '{}_output'.format(self.name)
            self.get_output_stream(output_name).send(output_msg)
        self._cnt += 1

    def execute(self):
        self._logger.info('Executing %s', self.name)
        self.spin()
