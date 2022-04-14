# pyharp

Harp implementation of the Harp protocol.

## Install with Pip
From this directory, install in editable mode with
````
pip install -e .
```

Note that for the above to work, a fairly recent version of pip (>= 21.3) is required.

## Install with Poetry

Each Python user has is own very dear IDE for editing. Here, we are leaving instructions on how to edit this code using pyCharm, Anaconda and Poetry.

The instructions are for beginner. Most of the users can just skip them.

This was tested on a Windows machine, but should be similar to other systems.


### 1. Install PyCHarm
**PyCharm** can be download from [here](https://www.jetbrains.com/pycharm/download/). The Community version is enough.
Download and install it.

### 2. Install Anaconda

**Anaconda** can be found [here](https://www.anaconda.com/products/individual).
Download the version according to your computer and install it.
- Unselect **Add Anaconda to the system PATH environment variable**
- Select ** Register Anaconda as the system Pyhton**

It's suggested to reboot your computer at this point

### 3. Install Poetry

Open the **Command Prompt** and execute the next command:
```
curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python
```

### 4. Install pyharp

Open **Anaconda**, navigate to the repository folder and execute the next commands:
```
poetry install
poetry env info
```

The second comand will reply with a **Path:**.
Select and copy this path.

### 5. Using PyCharm to edit the code

1. Open **PyCharm** :)
2. Go to File -> Open, select the repository folder, and click **OK**
3. Go to File -> Settings -> Project:pyharp -> Project Interpreter
3.1 Click in the gear in front of the Project Interpreter: and select **Add...**
3.2 On Virtualenv Environment, chose Existing environment
3.3 Select **python.exe** on the folder Scripts under  the path copied from the _poetry env info_ command
3.4 Click **OK** and **OK**

You are ready to go!

### 6. Test the code

Under **PyCharm**, Open one of the examples from the folder _examples_ (the _get_info.py_ is generic, so it's a good option) and update the COMx to your COM number.
Right-click on top of the file and chose option _Run 'get_info.py_. You should read something like this in the console:
```
Device info:
* Who am I: (2080) IblBehavior
* HW version: 1.0
* Assembly version: 0
* HARP version: 1.6
* Firmware version: 1.0
* Device user name: IBL_rig_0
```
