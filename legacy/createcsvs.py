#!/usr/bin/env python3
"""Take SVG files of individual plots and convert them to CSV."""
import os

import click
import pandas as pd
import svgpathtools
from matplotlib import pyplot as plt

Y_AXIS_SPAN = 80  # Distance in percentage points from baseline to upper and lower lines
X_AXIS_SPAN = 42  # Distance covered by x-axis in days


@click.command()
@click.argument("INPUT_FOLDER")
@click.argument("OUTPUT_FOLDER")
@click.argument("DATES_FILE")
@click.option(
    "-p",
    "--plots",
    is_flag=True,
    default=False,
    help="Enables creation and saving of additional PNG plots",
)
def main(input_folder, output_folder, dates_file, plots):
    """Turn SVG graphs into CSVs.

    Given an input folder of single plot SVGs convert them into CSV files.

    Args:
        input_folder: Location of SVG files
        output_folder: Location to store the CSVs
        dates_file: Lookup from x axis steps to date
        plots: Boolean flag
            Set to true to create png plots from the extracted data
            (used for manual inspection checks against source plots)
    """
    date_lookup_df = pd.read_csv(dates_file)

    location = input_folder.split("/")[-1]
    print(f"Loading data from location: {location}")

    os.makedirs(output_folder, exist_ok=True)

    for filename in os.listdir(input_folder):

        if filename.startswith("."):
            continue

        print(f"Getting paths from: {filename}")
        paths, _ = svgpathtools.svg2paths(os.path.join(input_folder, filename))

        # Gets paths from file
        xlim, y_lines, trend = categorise_paths(paths)

        trend_converted = convert_units(
            trend, y_lines, xlim, yspan=Y_AXIS_SPAN, xspan=X_AXIS_SPAN
        )

        filename = (
            f"{output_folder}/{input_folder.split('/')[-1]}-{filename.split('.')[0]}"
        )

        if trend_converted:
            xs, ys = tuple(zip(*trend_converted))
        else:
            xs = ys = []

        df = pd.DataFrame(data={"value": ys, "rel_day": xs})

        result_df = pd.merge(
            date_lookup_df, df, left_on="index", right_on="rel_day", how="left"
        )

        result_df = result_df[["value", "date"]]
        result_df["origin"] = location
        try:
            result_df["graph_num"] = filename.split(".")[0].split("-")[1]
        except IndexError:
            result_df["graph_num"] = filename.split(".")[0]

        result_df.to_csv(f"{filename}.csv", sep=",", index=False, float_format="%.3f")

        if plots:
            plt.plot(result_df.date, result_df.value)
            plt.ylim(-80, 80)
            plt.savefig(f"{filename}.png")

            plt.clf()


def categorise_paths(paths):
    """Categorise paths into background lines and the trend line.

    Args:
        paths: Paths extracted from single plot SVG

    Returns:
        (xlim, y_lines, points)
        xlim: Limits of the x axis (in SVG coordinates)
        y_lines: [Bottom, Middle, Top]
            i.e. (-80%, baseline, +80%) (in SVG coordinates)
        points: Points on the trend line (in SVG coordinates)

    Raises:
        ValueError: Assuming single segment trend line, not yet handled
    """
    single_segment_lines = [path for path in paths if len(path) == 1]

    short_trends = []
    if len(single_segment_lines) > 5:

        single_segment_lines.sort(key=lambda p: p.length())

        short_trends = single_segment_lines[:-5]
        single_segment_lines = single_segment_lines[:5]

    y_lines = sorted([path.start.imag for path in single_segment_lines])

    if len(y_lines) == 5:
        y_lines = [y_lines[0], y_lines[2], y_lines[-1]]

    points = []

    if len(y_lines) == 3:

        xlim = [(path.start.real, path.end.real) for path in paths if len(path) == 1][1]

        trends = [path for path in paths if len(path) > 1] + short_trends

        for trend in trends:
            if isinstance(trend[0], svgpathtools.path.CubicBezier):
                point_xmin, point_xmax, point_ymin, point_ymax = trend.bbox()
                xmid = (point_xmin + point_xmax) / 2
                ymid = (point_ymin + point_ymax) / 2

                points.append(complex(xmid, ymid))

            else:

                for sub_path in trend.continuous_subpaths():
                    points += [segment.start for segment in sub_path]
                    points.append(sub_path.end)

        y_lines = sorted(y_lines, reverse=True)

        return xlim, y_lines, points

    else:
        raise ValueError(f"Wrong number of y_lines: {len(y_lines)}")


def convert_units(trend, line_y, xlim, yspan, xspan):
    """witch from SVG coordinates to plot coordinates

    Args:
        trend: points on the trend line
        line_y: y SVG coords of (-80%, baseline, 80%) lines
        xlim: Limits of the x axis (SVG coordinates)
        yspan: Coordinate distance from baseline to outer y_lines
        xspan: Distance in whole days from start to end of the plot

    Returns:
        trend_plot_coords: List of (x, y) tuples
            Points on the trend line in plot coordinates
    """
    xmin, xmax = xlim
    x_scale = xmax - xmin

    ymax, ymid, ymin = tuple(line_y)
    y_scale = (abs(ymax - ymid) + abs(ymid - ymin)) / 2

    trend_plot_coords = []
    for point in trend:
        x = point.real
        y = point.imag

        x_out = 1 + round(xspan * ((x - xmin) / x_scale))
        y_out = yspan * ((ymid - y) / y_scale)

        trend_plot_coords.append((x_out, y_out))
    return trend_plot_coords


if __name__ == "__main__":
    main()
