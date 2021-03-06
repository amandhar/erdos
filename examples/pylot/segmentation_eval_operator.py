import heapq
import numpy as np

from carla.image_converter import labels_to_cityscapes_palette

from erdos.op import Op
from erdos.utils import setup_csv_logging, setup_logging, time_epoch_ms

from segmentation_utils import compute_semantic_iou
from pylot_utils import is_ground_segmented_camera_stream, is_segmented_camera_stream


class SegmentationEvalOperator(Op):

    def __init__(self, name, flags, log_file_name=None, csv_file_name=None):
        super(SegmentationEvalOperator, self).__init__(name)
        self._flags = flags
        self._logger = setup_logging(self.name, log_file_name)
        self._csv_logger = setup_csv_logging(self.name + '-csv', csv_file_name)
        self._last_seq_num_ground_segmented = -1
        self._last_seq_num_segmented = -1
        self._last_notification = -1
        # Buffer of ground truth segmented frames.
        self._ground_frames = []
        # Buffer of segmentation output frames.
        self._segmented_frames = []
        # Heap storing pairs of (ground/output time, game time).
        self._segmented_start_end_times = []
        self._sim_interval = None

    @staticmethod
    def setup_streams(input_streams,
                      ground_stream_name,
                      segmented_stream_name):
        input_streams.filter(is_ground_segmented_camera_stream).add_callback(
            SegmentationEvalOperator.on_ground_segmented_frame)
        input_streams.filter(is_segmented_camera_stream) \
                     .filter_name(segmented_stream_name) \
                     .add_callback(SegmentationEvalOperator.on_segmented_frame)
        # Register a watermark callback.
        input_streams.add_completion_callback(
            SegmentationEvalOperator.on_notification)
        return []

    def on_notification(self, msg):
        # Check that we didn't skip any notification. We only skip
        # notifications if messages or watermarks are lost.
        if self._last_notification != -1:
            assert self._last_notification + 1 == msg.timestamp.coordinates[1]
        self._last_notification = msg.timestamp.coordinates[1]

        # Ignore the first two messages. We use them to get sim time
        # between frames.
        if self._last_notification < 2:
            if self._last_notification == 0:
                self._sim_interval = int(msg.timestamp.coordinates[0])
            elif self._last_notification == 1:
                # Set he real simulation interval.
                self._sim_interval = int(msg.timestamp.coordinates[0]) - self._sim_interval
            return

        game_time = msg.timestamp.coordinates[0]
        while len(self._segmented_start_end_times) > 0:
            (end_time, start_time) = self._segmented_start_end_times[0]
            # We can compute mIoU if the end time is not greater than the
            # ground time.
            if end_time <= game_time:
                # This is the closest ground segmentation to the end time.
                heapq.heappop(self._segmented_start_end_times)
                end_frame = self.__get_ground_segmentation_at(end_time)
                self._logger.info('Computing for times {} {}'.format(
                    start_time, end_time))
                if self._flags.segmentation_eval_use_accuracy_model:
                    # Not using the segmentation output => get ground
                    # segmentation.
                    start_frame = self.__get_ground_segmentation_at(start_time)
                    self.__compute_mean_iou(end_frame, start_frame)
                else:
                    start_frame = self.__get_segmented_at(start_time)
                    self.__compute_mean_iou(end_frame, start_frame)
            else:
                # The remaining entries are newer ground segmentated frames.
                break

        self.__garbage_collect_segmentation()

    def on_ground_segmented_frame(self, msg):
        if self._last_seq_num_ground_segmented + 1 != msg.timestamp.coordinates[1]:
            self._logger.error('Expected msg with seq num {} but received {}'.format(
                (self._last_seq_num_ground_segmented + 1), msg.timestamp.coordinates[1]))
            if self._flags.fail_on_message_loss:
                assert self._last_seq_num_ground_segmented + 1 == msg.timestamp.coordinates[1]
        self._last_seq_num_ground_segmented = msg.timestamp.coordinates[1]

        if msg.timestamp.coordinates[1] >= 2:
            # Buffer the ground truth frames.
            game_time = msg.timestamp.coordinates[0]
            self._ground_frames.append((game_time, msg.data))

    def on_segmented_frame(self, msg):
        if self._last_seq_num_segmented + 1 != msg.timestamp.coordinates[1]:
            self._logger.error('Expected msg with seq num {} but received {}'.format(
                (self._last_seq_num_segmented + 1), msg.timestamp.coordinates[1]))
            if self._flags.fail_on_message_loss:
                assert self._last_seq_num_segmented + 1 == msg.timestamp.coordinates[1]
        self._last_seq_num_segmented = msg.timestamp.coordinates[1]
        # Ignore the first two messages. We use them to get sim time
        # between frames.
        if msg.timestamp.coordinates[1] < 2:
            return

        (frame, runtime) = msg.data
        game_time = msg.timestamp.coordinates[0]
        self._segmented_frames.append((game_time, frame))
        # Two metrics: 1) mIoU, and 2) timely-mIoU
        if self._flags.eval_segmentation_metric == 'mIoU':
            # We will compare with segmented ground frame with the same game
            # time.
            heapq.heappush(self._segmented_start_end_times,
                           (game_time, game_time))
        elif self._flags.eval_segmentation_metric == 'timely-mIoU':
            # Ground segmented frame time should be as close as possible to
            # the time game time + segmentation runtime.
            segmented_time = game_time + runtime
            if self._flags.segmentation_eval_use_accuracy_model:
                # Include the decay of segmentation with time if we do not
                # want to use the accuracy of our models.
                # TODO(ionel): We must pass model mIoU to this method.
                ground_frame_time += self.__mean_iou_to_latency(1)
            segmented_time = self.__compute_closest_frame_time(segmented_time)
            # Round time to nearest frame.
            heapq.heappush(self._segmented_start_end_times,
                           (segmented_time, game_time))
        else:
            self._logger.fatal('Unexpected segmentation metric {}'.format(
                self._flags.eval_segmentation_metric))

    def execute(self):
        self.spin()

    def __compute_closest_frame_time(self, time):
        base = int(time) / self._sim_interval * self._sim_interval
        if time - base < self._sim_interval / 2:
            return base
        else:
            return base + self._sim_interval

    def __compute_mean_iou(self, ground_frame, segmented_frame):
        # Transfrom the ground frame to Cityscapes palette; the segmented
        # frame is transformed by segmentation operators.
        ground_frame = labels_to_cityscapes_palette(ground_frame)
        (mean_iou, class_iou) = compute_semantic_iou(ground_frame,
                                                     segmented_frame)
        self._logger.info('IoU class scores: {}'.format(class_iou))
        self._logger.info('mean IoU score: {}'.format(mean_iou))
        self._csv_logger.info('{},{},{},{}'.format(
            time_epoch_ms(), self.name, self._flags.eval_segmentation_metric,
            mean_iou))

    def __mean_iou_to_latency(self, mean_iou):
        """ Function that gives a latency estimate of how much
        simulation time must pass such that a 1.0 IoU decays to mean_iou.
        """
        # TODO(ionel): Implement!
        return 0

    def __get_ground_segmentation_at(self, timestamp):
        for (time, frame) in self._ground_frames:
            if time == timestamp:
                return frame
            elif time > timestamp:
                break
        self._logger.fatal(
            'Could not find ground segmentation for {}'.format(timestamp))

    def __get_segmented_at(self, timestamp):
        for (time, frame) in self._segmented_frames:
            if time == timestamp:
                return frame
            elif time > timestamp:
                break
        self._logger.fatal(
            'Could not find segmentaed frame for {}'.format(timestamp))

    def __garbage_collect_segmentation(self):
        # Get the minimum watermark.
        watermark = None
        for (_, start_time) in self._segmented_start_end_times:
            if watermark is None or start_time < watermark:
                watermark = start_time
        if watermark is None:
            return
        # Remove all segmentations that are below the watermark.
        index = 0
        while (index < len(self._segmented_frames) and
               self._segmented_frames[index][0] < watermark):
            index += 1
        if index > 0:
            self._segmented_frames = self._segmented_frames[index:]
        # Remove all the ground segmentations that are below the watermark.
        index = 0
        while (index < len(self._ground_frames) and
               self._ground_frames[index][0] < watermark):
            index += 1
        if index > 0:
            self._ground_frames = self._ground_frames[index:]
