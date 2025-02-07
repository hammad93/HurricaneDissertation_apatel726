# HURAIM

**Hur**ricane **A**rtificial **I**ntelligence using **M**achine Learning 

## Git Quickstart

First, we open up a terminal and double check if we have git installed. 
Then, we can clone the code using this command and git. These commands 
are meant to be run inside the same directory. Currently, Github hosts
our git repository.

```bash
git clone https://github.com/apatel726/HurricaneDissertation.git
```
When we make changes, we can see them here.

```bash
git diff
```
After confirming the changes, we can add them, or add all of the changes like here,

```bash
git add -A
```
Before uploading the changes, they all need a message pertaining to the development
of the code. 

```bash
git commit -m "Out of a mountain of despair, a stone of hope."
```
This command uploads the code to the main branch. If you are on a different branch,
it is the same command to upload to the same branch on GitHub.

```bash
git push
```

## Quickstart

Model Creation Command Line Arguments
----------------------------

Create the model specified with the command line. e.g.

    >>> python run.py --universal
    >>> python run.py --singular

Accepts command line argument as either,
    universal
        Creates a universal model with wind intensity, lat, and long
    singular
        Creates singular models with 3 different models for wind, lat and long
If none are specified, we create a universal model

Training Command Line Arguments
-------------------------------

`--load`

If there are models in the ml/models directory, we will use the files and weights in them according to the mode

        >>> python run.py                       # trains the artificial intelligence
        >>> python run.py --load                # loads the universal model weights
        >>> python run.py --singular --load     # loads the singular model weights
`--epochs [int]`

The number of epochs to train the model

        >>> python run.py --singular --epochs 100
Tutorial

    python run.py -h
    usage: run.py [-h] [--singular] [--universal] [--load] [--epochs EPOCHS] [--dropout DROPOUT] [--loss LOSS] [--optimizer OPTIMIZER]

    optional arguments:
      -h, --help            show this help message and exit
      --singular            The 'singular' version of the architecture will be used
      --universal           The 'universal' version of the architecture will be used in ml/models
      --load                Loads existing model weights in the repository
      --epochs EPOCHS       Number of epochs to train the model
      --dropout DROPOUT     The dropout hyperparameter
      --loss LOSS           The loss hyperparameter
      --optimizer OPTIMIZER
                            The optimizer hyperparameter
                            
Tensorboard Quickstart
----------------------

Tensorboard utilizes the 6006 port and we will need to have that open during our docker run such as,

```bash
docker run -it -p 8888:8888 -p 6006:6006 huraim
```

Enter in the following command inside a Jupyterlab terminal from the Docker setup,

```bash
tensorboard --logdir /tf/HurricaneDissertation/hurricane_ai/models/ --bind_all
```

## Docker Quickstart

_Please note that this was taken from the docker/Docker.md file. Reference it for the most up to date documentation_


Install Docker first. This Dockerfile should work on any OS. Please note that
the following commands should be run inside the `docker` folder.

```bash
docker build -t huraim .
docker run --gpus all -it -p 8888:8888 -p 6006:6006 huraim
```

The above enables GPU. If GPU's are not available, replace with the following command,
```bash
docker run -it -p 8888:8888 -p 6006:6006 huraim
```

After running the above commands, open up a web browser and go to
`localhost:8888`. 

Creation Predictions Quickstart
----------------------


Tutorial

Test File Prediction

`python "test.py" --config "name of file to load configuration" --test "location of test file"`

`python test.py --config data/config.json --test data/hurdat2_test.txt`

Live Hurricane Prediction

`python "test.py" --config "name of file to load configuration" --test "location of test file"`

`python test.py --config data/config.json --test data/hurdat2_test.txt`
