import numpy as np
import open3d.ml as _ml3d
import math

from open3d.ml.vis import Visualizer, BoundingBox3D, LabelLUT  #, BEVBox3D
from open3d.ml.datasets import KITTI, NuScenes, Argoverse, Lyft, Waymo

import argparse
from tqdm import tqdm


def parse_args():
    parser = argparse.ArgumentParser(
        description='Demo for inference of object detection')
    parser.add_argument('framework',
                        help='deep learning framework: tf or torch')
    parser.add_argument('dataset_name', help='name of dataset in lower case')
    parser.add_argument('--dataset_path', help='path to dataset', required=True)
    parser.add_argument('--info_path',
                        help='path to dataset',
                        required=False,
                        default=None)
    parser.add_argument('--ckpt_pointpillars_path',
                        help='path to PointPillars checkpoint'),
    parser.add_argument('--split',
                        help='training/train, validation/val or testing/test',
                        required=False,
                        default='training')
    parser.add_argument('--device',
                        help='device to run the pipeline',
                        default='gpu')

    args, _ = parser.parse_known_args()

    dict_args = vars(args)
    for k in dict_args:
        v = dict_args[k]
        print("{}: {}".format(k, v) if v is not None else "{} not given".
              format(k))

    return args


def main(args):

    framework = _ml3d.utils.convert_framework_name(args.framework)
    args.device = _ml3d.utils.convert_device_name(args.device)
    if framework == 'torch':
        import open3d.ml.torch as ml3d
        from ml3d.torch.dataloaders import TorchDataloader as Dataloader
    else:
        import tensorflow as tf
        import open3d.ml.tf as ml3d

        from ml3d.tf.dataloaders import TFDataloader as Dataloader

        device = args.device
        gpus = tf.config.experimental.list_physical_devices('GPU')
        if gpus:
            try:
                for gpu in gpus:
                    tf.config.experimental.set_memory_growth(gpu, True)
                if device == 'cpu':
                    tf.config.set_visible_devices([], 'GPU')
                elif device == 'gpu':
                    tf.config.set_visible_devices(gpus[0], 'GPU')
                else:
                    idx = device.split(':')[1]
                    tf.config.set_visible_devices(gpus[int(idx)], 'GPU')
            except RuntimeError as e:
                print(e)

    ObjectDetection = _ml3d.utils.get_module("pipeline", "ObjectDetection",
                                             framework)
    PointPillars = _ml3d.utils.get_module("model", "PointPillars", framework)

    which = args.dataset_name
    path = args.dataset_path
    info_path = args.info_path

    if which == "kitti":
        dataset = KITTI(path, info_path=info_path)
        cfg = _ml3d.utils.Config.load_from_file(
            "ml3d/configs/pointpillars_kitti.yml")
    elif which == "nuscenes":
        dataset = NuScenes(path, info_path=info_path)
        cfg = _ml3d.utils.Config.load_from_file(
            "ml3d/configs/pointpillars_nuscenes.yml")
    elif which == "lyft":
        dataset = Lyft(path, info_path=info_path)
        cfg = _ml3d.utils.Config.load_from_file(
            "ml3d/configs/pointpillars_lyft.yml")
    elif which == "argoverse":
        dataset = Argoverse(path, info_path=info_path)
        cfg = _ml3d.utils.Config.load_from_file(
            "ml3d/configs/pointpillars_argoverse.yml")
    elif which == "waymo":
        dataset = Waymo(path, info_path=info_path)
        cfg = _ml3d.utils.Config.load_from_file(
            "ml3d/configs/pointpillars_waymo.yml")

    model = PointPillars(device=args.device, **cfg.model)
    pipeline = ObjectDetection(model, dataset, device=args.device)

    # load the parameters.
    pipeline.load_ckpt(ckpt_path=args.ckpt_pointpillars_path)

    test_split = Dataloader(dataset=dataset.get_split(args.split),
                            preprocess=model.preprocess,
                            transform=None,
                            use_cache=False,
                            shuffle=False)

    # run inference on a single example.
    data = test_split[5]['data']
    result = pipeline.run_inference(data)[0]

    boxes = data['bbox_objs']
    boxes.extend(result)

    vis = Visualizer()

    lut = LabelLUT()
    for val in sorted(dataset.label_to_names.keys()):
        lut.add_label(val, val)
    # Uncommenting this assigns bbox color according to lut
    # for key, val in sorted(dataset.label_to_names.items()):
    #     lut.add_label(key, val)

    vis.visualize([{
        "name": which,
        'points': data['point']
    }],
                  lut,
                  bounding_boxes=boxes)

    # run inference on a multiple examples
    vis = Visualizer()
    lut = LabelLUT()
    for val in sorted(dataset.label_to_names.keys()):
        lut.add_label(val, val)

    boxes = []
    data_list = []
    for idx in tqdm(range(100)):
        data = test_split[idx]['data']

        result = pipeline.run_inference(data)[0]

        boxes = data['bbox_objs']
        boxes.extend(result)

        data_list.append({
            "name": which + '_' + str(idx),
            'points': data['point'],
            'bounding_boxes': boxes
        })

    vis.visualize(data_list, lut, bounding_boxes=None)


if __name__ == '__main__':
    args = parse_args()
    main(args)
