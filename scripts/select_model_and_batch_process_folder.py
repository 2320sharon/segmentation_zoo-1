# Written by Dr Daniel Buscombe, Marda Science LLC
# for the USGS Coastal Change Hazards Program
#
# MIT License
#
# Copyright (c) 2022, Marda Science LLC
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import sys,os, json
from tkinter import filedialog
from tkinter import *
import requests
from glob import glob
from tqdm import tqdm

def download_url(url, save_path, chunk_size=128):
    r = requests.get(url, stream=True)
    with open(save_path, 'wb') as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
            fd.write(chunk)

#### choose zenodo release
root = Tk()
choices = ['sat_RGB_2class_7384255', 'sat_5band_2class_7388008', 
            'sat_RGB_4class_6950472', 'sat_5band_4class_7344606', 
            'sat_NDWI_4class_7352859', 'sat_MNDWI_4class_7352850', 'sat_7band_4class_7358284',
            'aerial_2class_6234122', 'aerial_2class_6235090', 'ortho_2class_6410157']

variable = StringVar(root)
variable.set('sat_RGB_4class_6950472')
w = OptionMenu(root, variable, *choices)
w.pack(); root.mainloop()

dataset_id = variable.get()
print("Dataset ID : {}".format(dataset_id))

zenodo_id = dataset_id.split('_')[-1]
print("Zenodo ID : {}".format(zenodo_id))

## choose model implementation type
root = Tk()
choices = ['BEST','ENSEMBLE']
variable = StringVar(root)
variable.set('ENSEMBLE')
w = OptionMenu(root, variable, *choices)
w.pack(); root.mainloop()

model_choice = variable.get()
print("Model implementation choice : {}".format(model_choice))

####======================================
try:
    os.mkdir('../downloaded_models')
except:
    pass

try:
    os.mkdir('../downloaded_models/'+dataset_id)
except:
    pass

model_direc = '../downloaded_models/'+dataset_id

root_url = 'https://zenodo.org/api/records/'+zenodo_id

r = requests.get(root_url)

js = json.loads(r.text)
files = js['files']

if model_choice=='BEST':
    # grab just the best model text file
    best_model_txt = [f for f in files if f['key']=='BEST_MODEL.txt']
    download_url(best_model_txt[0]['links']['self'], model_direc + os.sep + 'BEST_MODEL.txt')
    # read in that file 
    with open(model_direc + os.sep + 'BEST_MODEL.txt') as f:
        dat = f.read()

    # get best model and download it
    best_model_h5 = [f for f in files if f['key']==dat]
    outfile = model_direc + os.sep + dat
    if not os.path.isfile(outfile):
        print("Downloading file to {}".format(outfile))
        download_url(best_model_h5[0]['links']['self'], outfile)

    # get best model config and download it
    best_model_json = [f for f in files if f['key']==dat.replace('_fullmodel.h5','.json')]
    outfile = model_direc + os.sep + dat.replace('_fullmodel.h5','.json')
    if not os.path.isfile(outfile):
        print("Downloading file to {}".format(outfile))
        download_url(best_model_json[0]['links']['self'], outfile)

else:
    # get list of all models
    all_models = [f for f in files if f['key'].endswith('.h5')]

    # download all weights
    for a in all_models:
        outfile = model_direc + os.sep + a['links']['self'].split('/')[-1]
        if not os.path.isfile(outfile):
            print("Downloading file to {}".format(outfile))
            download_url(a['links']['self'], outfile)

    # download all con fig
    for a in all_models:
        outfile = model_direc + os.sep + a['links']['self'].split('/')[-1]
        outfile = outfile.replace('_fullmodel.h5','.json')
        if not os.path.isfile(outfile):
            print("Downloading file to {}".format(outfile))
            download_url(a['links']['self'].replace('_fullmodel.h5','.json'), outfile)


###==============================================

root = Tk()
root.filename =  filedialog.askdirectory(title = "Select directory of images (or npzs) to segment")
sample_direc = root.filename
print(sample_direc)
root.withdraw()

#####################################
#### concatenate models
####################################

# W : list containing all the weight files fill paths
W=[]

if model_choice=='ENSEMBLE':
    W= glob(model_direc+os.sep+'*.h5')
    print("{} sets of model weights were found ".format(len(W)))
else:
    #read best model file
    #select weights
    with open(model_direc+os.sep+'BEST_MODEL.txt') as f:
        w = f.readlines()
    W = [model_direc + os.sep + w[0]]


# For each set of weights in W load them in
M= []; C=[]; T = []
for counter,weights in enumerate(W):

    try:
        # "fullmodel" is for serving on zoo they are smaller and more portable between systems than traditional h5 files
        # gym makes a h5 file, then you use gym to make a "fullmodel" version then zoo can read "fullmodel" version
        configfile = weights.replace('_fullmodel.h5','.json').replace('weights', 'config')
        with open(configfile) as f:
            config = json.load(f)
    except:
        # Turn the .h5 file into a json so that the data can be loaded into dynamic variables        
        configfile = weights.replace('.h5','.json').replace('weights', 'config')
        with open(configfile) as f:
            config = json.load(f)
    # Dynamically creates all variables from config dict.
    # For example configs's {'TARGET_SIZE': [768, 768]} will be created as TARGET_SIZE=[768, 768]
    # This is how the program is able to use variables that have never been explicitly defined
    for k in config.keys():
        exec(k+'=config["'+k+'"]')


    if counter==0:
        #####################################
        #### hardware
        ####################################

        SET_GPU = str(SET_GPU)

        if SET_GPU != '-1':
            USE_GPU = True
            print('Using GPU')
        else:
            USE_GPU = False
            print('Using CPU')

        if len(SET_GPU.split(','))>1:
            USE_MULTI_GPU = True 
            print('Using multiple GPUs')
        else:
            USE_MULTI_GPU = False
            if USE_GPU:
                print('Using single GPU device')
            else:
                print('Using single CPU device')

        #suppress tensorflow warnings
        os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

        if USE_GPU == True:
            os.environ['CUDA_VISIBLE_DEVICES'] = SET_GPU

            from doodleverse_utils.prediction_imports import *
            from tensorflow.python.client import device_lib
            physical_devices = tf.config.experimental.list_physical_devices('GPU')
            print(physical_devices)

            if physical_devices:
                # Restrict TensorFlow to only use the first GPU
                try:
                    tf.config.experimental.set_visible_devices(physical_devices, 'GPU')
                except RuntimeError as e:
                    # Visible devices must be set at program startup
                    print(e)
        else:
            os.environ['CUDA_VISIBLE_DEVICES'] = '-1'

            from doodleverse_utils.prediction_imports import *
            from tensorflow.python.client import device_lib
            physical_devices = tf.config.experimental.list_physical_devices('GPU')
            print(physical_devices)

        ### mixed precision
        from tensorflow.keras import mixed_precision
        mixed_precision.set_global_policy('mixed_float16')
        # tf.debugging.set_log_device_placement(True)

        for i in physical_devices:
            tf.config.experimental.set_memory_growth(i, True)
        print(tf.config.get_visible_devices())

        if USE_MULTI_GPU:
            # Create a MirroredStrategy.
            strategy = tf.distribute.MirroredStrategy([p.name.split('/physical_device:')[-1] for p in physical_devices], cross_device_ops=tf.distribute.HierarchicalCopyAllReduce())
            print("Number of distributed devices: {}".format(strategy.num_replicas_in_sync))


    #from imports import *
    from doodleverse_utils.imports import *
    from doodleverse_utils.model_imports import *

    #---------------------------------------------------

    #=======================================================
    # Import the architectures for following models from doodleverse_utils
    # 1. custom_resunet
    # 2. custom_unet
    # 3. simple_resunet
    # 4. simple_unet
    # 5. satunet
    # 6. custom_resunet
    # 7. custom_satunet

    # Get the selected model based on the weights file's MODEL key provided
    # create the model with the data loaded in from the weights file
    print('.....................................')
    print('Creating and compiling model {}...'.format(counter))

    if MODEL =='resunet':
        model =  custom_resunet((TARGET_SIZE[0], TARGET_SIZE[1], N_DATA_BANDS),
                        FILTERS,
                        nclasses=NCLASSES, #[NCLASSES+1 if NCLASSES==1 else NCLASSES][0],
                        kernel_size=(KERNEL,KERNEL),
                        strides=STRIDE,
                        dropout=DROPOUT,
                        dropout_change_per_layer=DROPOUT_CHANGE_PER_LAYER,
                        dropout_type=DROPOUT_TYPE,
                        use_dropout_on_upsampling=USE_DROPOUT_ON_UPSAMPLING,
                        )
    elif MODEL=='unet':
        model =  custom_unet((TARGET_SIZE[0], TARGET_SIZE[1], N_DATA_BANDS),
                        FILTERS,
                        nclasses=NCLASSES, #[NCLASSES+1 if NCLASSES==1 else NCLASSES][0],
                        kernel_size=(KERNEL,KERNEL),
                        strides=STRIDE,
                        dropout=DROPOUT,
                        dropout_change_per_layer=DROPOUT_CHANGE_PER_LAYER,
                        dropout_type=DROPOUT_TYPE,
                        use_dropout_on_upsampling=USE_DROPOUT_ON_UPSAMPLING,
                        )

    elif MODEL =='simple_resunet':

        model = simple_resunet((TARGET_SIZE[0], TARGET_SIZE[1], N_DATA_BANDS),
                    kernel = (2, 2),
                    num_classes=NCLASSES, #[NCLASSES+1 if NCLASSES==1 else NCLASSES][0],
                    activation="relu",
                    use_batch_norm=True,
                    dropout=DROPOUT,
                    dropout_change_per_layer=DROPOUT_CHANGE_PER_LAYER,
                    dropout_type=DROPOUT_TYPE,
                    use_dropout_on_upsampling=USE_DROPOUT_ON_UPSAMPLING,
                    filters=FILTERS,
                    num_layers=4,
                    strides=(1,1))

    elif MODEL=='simple_unet':
        model = simple_unet((TARGET_SIZE[0], TARGET_SIZE[1], N_DATA_BANDS),
                    kernel = (2, 2),
                    num_classes=NCLASSES, #[NCLASSES+1 if NCLASSES==1 else NCLASSES][0],
                    activation="relu",
                    use_batch_norm=True,
                    dropout=DROPOUT,
                    dropout_change_per_layer=DROPOUT_CHANGE_PER_LAYER,
                    dropout_type=DROPOUT_TYPE,
                    use_dropout_on_upsampling=USE_DROPOUT_ON_UPSAMPLING,
                    filters=FILTERS,
                    num_layers=4,
                    strides=(1,1))

    elif MODEL=='satunet':

        model = custom_satunet((TARGET_SIZE[0], TARGET_SIZE[1], N_DATA_BANDS),
                    kernel = (2, 2),
                    num_classes=NCLASSES, #[NCLASSES+1 if NCLASSES==1 else NCLASSES][0],
                    activation="relu",
                    use_batch_norm=True,
                    dropout=DROPOUT,
                    dropout_change_per_layer=DROPOUT_CHANGE_PER_LAYER,
                    dropout_type=DROPOUT_TYPE,
                    use_dropout_on_upsampling=USE_DROPOUT_ON_UPSAMPLING,
                    filters=FILTERS,
                    num_layers=4,
                    strides=(1,1))

    else:
        print("Model must be one of 'unet', 'resunet', or 'satunet'")
        sys.exit(2)

    try:
        # Load in the model from the weights which is the location of the weights file        
        model = tf.keras.models.load_model(weights)

        M.append(model)
        C.append(configfile)
        T.append(MODEL)
        
    except:
        # Load the metrics mean_iou, dice_coef from doodleverse_utils
        # Load in the custom loss function from doodleverse_utils        
        model.compile(optimizer = 'adam', loss = dice_coef_loss(NCLASSES))#, metrics = [iou_multi(NCLASSES), dice_multi(NCLASSES)])

        model.load_weights(weights)

        M.append(model)
        C.append(configfile)
        T.append(MODEL)

# metadatadict contains the model name (T) the config file(C) and the model weights(W)
metadatadict = {}
metadatadict['model_weights'] = W
metadatadict['config_files'] = C
metadatadict['model_types'] = T

#####################################
#### read images
####################################

# The following lines prepare the data to be predicted
sample_filenames = sorted(glob(sample_direc+os.sep+'*.*'))
if sample_filenames[0].split('.')[-1]=='npz':
    sample_filenames = sorted(tf.io.gfile.glob(sample_direc+os.sep+'*.npz'))
else:
    sample_filenames = sorted(tf.io.gfile.glob(sample_direc+os.sep+'*.jpg'))
    if len(sample_filenames)==0:
        sample_filenames = sorted(glob(sample_direc+os.sep+'*.png'))

print('Number of samples: %i' % (len(sample_filenames)))

#####################################
#### run model on each image in a for loop
####################################
### predict
print('.....................................')
print('Using model for prediction on images ...')

#look for TTA config
if not 'TESTTIMEAUG' in locals():
    print("TESTTIMEAUG not found in config file(s). Setting to False")
    TESTTIMEAUG = False

if not 'WRITE_MODELMETADATA' in locals():
    print("WRITE_MODELMETADATA not found in config file(s). Setting to False")
    WRITE_MODELMETADATA = False
if not 'OTSU_THRESHOLD' in locals():
    print("OTSU_THRESHOLD not found in config file(s). Setting to False")
    OTSU_THRESHOLD = False

# Import do_seg() from doodleverse_utils to perform the segmentation on the images
for f in tqdm(sample_filenames):
    try:
        do_seg(f, M, metadatadict, sample_direc,NCLASSES,N_DATA_BANDS,TARGET_SIZE,TESTTIMEAUG, WRITE_MODELMETADATA,OTSU_THRESHOLD)
    except:
        print("{} failed. Check config file, and check the path provided contains valid imagery".format(f))


