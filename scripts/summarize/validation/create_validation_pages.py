from pathlib import Path
import toml
import os, sys

import shutil, time
import nbformat
from nbconvert.preprocessors import ExecutePreprocessor

config = toml.load(os.path.join(os.getcwd(), "configuration/validation_configuration.toml"))

def run_ipynb(sheet_name, nb_path):
    start_time = time.time()
    print("creating " + sheet_name + " page")
    with open(Path(nb_path) / (sheet_name + ".ipynb")) as f:
        nb = nbformat.read(f, as_version=4)
        if sys.version_info > (3, 0):
            py_version = "python3"
        else:
            py_version = "python2"
        ep = ExecutePreprocessor(timeout=1500, kernel_name=py_version)
        ep.preprocess(nb, {"metadata": {"path": Path(nb_path)}})
        with open(Path(nb_path) / (sheet_name + ".ipynb"), "wt") as f:
            nbformat.write(nb, f)
    end_time = time.time()
    print("Time taken to create " + sheet_name + " page: " + str(end_time - start_time) + " seconds")


def create_quarto_notebook(notebook_name, summary_list, scripts_dir, output_folder):
    # Try to remove existing data first
    output_dir = Path.cwd() / output_folder / notebook_name
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)

    for sheet_name in summary_list:
        run_ipynb(sheet_name, scripts_dir + "/validation_scripts")

    # render quarto book
    # TODO: automate _quarto.yml chapter list
    text = "quarto render " + scripts_dir
    os.system(text)
    print(notebook_name + " created")

    # Move these files to output folder
    if not os.path.exists(Path.cwd() / output_folder):
        os.makedirs(Path.cwd() / output_folder)
    shutil.move(Path.cwd() / scripts_dir / notebook_name, output_dir)

def main():

    # create validation notebook
    create_quarto_notebook(notebook_name = "validation-notebook",
                           summary_list = config["summary_list"][:1],
                           scripts_dir = "scripts/summarize/validation",
                           output_folder = config["p_output_dir"])
    

    ## separate notebook for telecommute analysis
    if "../telecommute_analysis/telecommute_analysis" in config["summary_list"]:
        # Try to remove existing data first
        telecommute_analysis_output_dir = os.path.join(os.getcwd(), config["p_output_dir"], "telecommute-analysis-notebook")
        if os.path.exists(telecommute_analysis_output_dir):
            shutil.rmtree(telecommute_analysis_output_dir)

        text = "quarto render scripts/summarize/validation/telecommute_analysis"
        os.system(text)
        print("telecommute analysis notebook created")

        # Move these files to output folder
        if not os.path.exists(os.path.join(os.getcwd(), config["p_output_dir"])):
            os.makedirs(os.path.join(os.getcwd(), config["p_output_dir"]))
        shutil.move(
            os.path.join(os.getcwd(), "scripts/summarize/validation/telecommute-analysis-notebook"),
            telecommute_analysis_output_dir,
        )


if __name__ == "__main__":
    main()