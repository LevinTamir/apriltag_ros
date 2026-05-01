# Calibrating the Intel RealSense D435i for AprilTag Pose Estimation

AprilTag pose accuracy depends entirely on the camera intrinsics published in
`/camera/camera/color/camera_info`. This document explains when factory
calibration is enough, how to verify it, and how to compute and apply a custom
calibration if you need better accuracy.

## TL;DR

1. **Try factory intrinsics first** — they are written to the D435i flash at
   the factory and published automatically by `realsense2_camera`.
2. **Verify** by holding a tag at a known distance (use a tape measure) and
   checking that `dist=` printed by `pose_printer` matches.
3. **Recalibrate** only if the error is larger than ~2% of distance, the lens
   has been bumped, or you are doing high-precision work (sub-cm).

## 1. What intrinsics are published

`realsense2_camera` reads the factory calibration from the camera firmware
and republishes it on:

```
/camera/camera/color/camera_info   # used by AprilTagNode
```

The `P` (projection) matrix in this message is what `AprilTagNode` consumes.
You can dump it with:

```bash
ros2 topic echo --once /camera/camera/color/camera_info
```

The diagonal of `P` (`P[0]`, `P[5]`) is the focal length in pixels; for the
D435i at 1920x1080 this is typically ~1380–1410 px.

## 2. Verifying the factory calibration

This is a 30-second sanity check, do this before bothering with recalibration.

1. Launch the pipeline:
   ```bash
   ros2 launch apriltag_ros apriltag_realsense.launch.py tag_size_mm:=64
   ```
2. Tape a tag flat to a wall.
3. Measure the distance from the **front glass of the D435i** to the **center
   of the tag** with a tape measure. Aim for ~1.0 m for a good test.
4. Read `dist=` from the `pose_printer` output.
5. Expected error on a healthy D435i is **< 1–2%** (e.g. 1.000 m measured →
   0.985 to 1.015 m reported).

If the reported distance is consistently off by more than ~3%, either the
`tag_size_mm` arg is wrong (re-measure the tag's outer black border with
calipers) or the intrinsics need recalibration.

> ⚠️ The most common cause of "wrong distance" is **wrong tag size** — not
> wrong calibration. Re-measure the tag before assuming the camera is at
> fault.

## 3. Custom calibration with a checkerboard

Use this if step 2 showed a large, consistent error.

### 3.1 Print a target

Download an OpenCV-style checkerboard:

```
https://docs.opencv.org/4.x/pattern.png
```

Print it on **rigid backing** (foamboard, plywood) — paper alone warps and
ruins calibration. The standard sizes:

| Pattern        | Inner corners | Square edge |
|----------------|---------------|-------------|
| Default OpenCV | 9 x 6         | measure!    |

Measure the actual printed square size with calipers. Common A3-printed
output is ~30 mm; do not trust the nominal value.

### 3.2 Install the calibration tool

```bash
sudo apt install ros-jazzy-camera-calibration
```

### 3.3 Run the calibration

In one terminal, start the camera only (no AprilTag node):

```bash
ros2 launch realsense2_camera rs_launch.py \
    enable_color:=true enable_depth:=false \
    rgb_camera.color_profile:=1920x1080x30
```

In another terminal, launch the calibrator. **Adjust `--size` and `--square`
to your printed board.**

```bash
ros2 run camera_calibration cameracalibrator \
    --size 8x5 \
    --square 0.030 \
    --ros-args -r image:=/camera/camera/color/image_raw \
               -r camera:=/camera/camera/color
```

> Note: `--size 8x5` means 8x5 *inner corners* (9x6 squares).

A GUI window appears with X/Y/Size/Skew bars. Move the board so each bar
fills:

- **X / Y** — board across full width and height of the image
- **Size** — board close, then far (fills frame, then small)
- **Skew** — tilt board left/right and up/down

Aim for ~40 captured images. The "CALIBRATE" button activates once the bars
are sufficiently full. Click **CALIBRATE**, wait ~30 s, then **SAVE** — this
writes `/tmp/calibrationdata.tar.gz`.

### 3.4 Apply the calibration

Extract the archive:

```bash
mkdir -p ~/.ros/camera_info
tar -xzf /tmp/calibrationdata.tar.gz -C /tmp/
cp /tmp/ost.yaml ~/.ros/camera_info/d435i_color.yaml
```

Edit the first line of `~/.ros/camera_info/d435i_color.yaml` so the
`camera_name` matches what `realsense2_camera` expects (typically
`color` or the device serial). The exact name comes from the
`camera_info` topic — the calibrator embeds whichever it received.

Tell `realsense2_camera` to load it via the `camera_info_url` launch
argument:

```bash
ros2 launch apriltag_ros apriltag_realsense.launch.py \
    tag_size_mm:=64 \
    camera_info_url:=file://$HOME/.ros/camera_info/d435i_color.yaml
```

(If `apriltag_realsense.launch.py` does not yet forward
`camera_info_url`, add it to the `realsense` `IncludeLaunchDescription`'s
`launch_arguments`.)

### 3.5 Re-verify

Repeat section 2. Expect distance error to drop below 1%.

## 4. When to recalibrate

| Trigger                                              | Recalibrate? |
|------------------------------------------------------|--------------|
| New D435i out of the box                             | No           |
| Camera was dropped or the lens housing took a knock  | Yes          |
| Operating temperature very different from indoor lab | Maybe        |
| Sub-cm pose accuracy required at >1 m range          | Yes          |
| Switching to a different `color_profile` resolution  | Re-verify    |

Note: D435i intrinsics are stored per-resolution. If you switch from
1920x1080 to 1280x720, both factory cal and any custom cal you saved must be
matched to that resolution.

## 5. Troubleshooting

- **`pose_printer` shows huge wobble / NaN** — usually a calibration that
  wasn't loaded (check `ros2 topic echo --once /camera/camera/color/camera_info`
  shows the values you expect).
- **All tags reported at the same distance regardless of true distance** —
  `tag_size_mm` is wrong; re-measure with calipers.
- **Distance OK, but x/y axes are off** — the principal point (`P[2]`,
  `P[6]`) is wrong, recalibrate.
- **Calibrator never gets a CALIBRATE button** — the X/Y/Size/Skew bars
  aren't full; move the board more aggressively.
