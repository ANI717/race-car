#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Race-car Deep Learning Class.

This script contains all deep learning tools to train and predict speed and 
steering value from a provided image. 

Revision History:
        2020-05-10 (Animesh): Baseline Software.
        2020-07-30 (Animesh): Updated Docstring.

Example:
        from rc_nn_tools import NNTools

"""


#___Import Modules:
import os
import json
import timeit
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import torch
from torch import nn, optim
from torch.utils.data import DataLoader

from rc_nn_utility import Datagen, ParseData
from racecarNet import ServoNet, MotorNet


#___Global Variables:
TYPE = ["servo", "test"]
SETTINGS = 'settings.json'
ODIR = "output/"
SEED = 717


#__Classes:
class NNTools:
    """Neural Network Tool Class.
    
    This class contains all methods to complete whole deep learing session
    containing training, testing and prediction-make sessions.
    
    """

    def __init__(self, settings=SETTINGS, types=TYPE):
        """Constructor.
        
        Args:
            settings (JSON file): Contains all settings manually provided.
            types (list): Contains settings to determine the session is for
                training or testing.

        """

        self.type = types[0]

        # extract JSON file contents
        with open(settings) as fp:
            content = json.load(fp)[types[0]][types[1]]

            self.shape = content["shape"]            
            self.batch_size = content["batch"]
            self.cuda = content["cuda"]

            if types[1] == "train":
                self.epochs = content["epoch"]
            elif types[1] == "test":
                self.model_file = content["model"]

        # set neural net by type
        torch.manual_seed(SEED)
        if self.type == "servo":
            self.model = ServoNet(self.shape)
        elif self.type == "motor":
            self.model = MotorNet(self.shape)

        if types[1] == "train":
            self.log = self.set_output()
        else:
            self.load_model(self.model_file)

        # set output folders and required classes
        self.parsedata = ParseData()
        self.datagen = Datagen(shape=self.shape)

        return None


    def set_output(self):
        """Output Manager.
        
        This method checks files and directories for producing output during
        training session and creates them if they don't exist.
        
        Returns:
            log (file): Location of log file to dump results during training 
                session.

        """

        # checks and creates output directories
        if not os.path.exists(ODIR):
            os.mkdir(ODIR)        
        if not os.path.exists(os.path.join(ODIR,"curves")):
            os.mkdir(os.path.join(ODIR,"curves"))        
        if not os.path.exists(os.path.join(ODIR,"models")):
            os.mkdir(os.path.join(ODIR,"models"))

        # checks and creates log file to dump results
        log = os.path.join(ODIR,"result.csv")
        if os.path.exists(log):
            os.remove(log)
            open(log, 'a').close()
        else:
            open(log, 'a').close()

        return log


    def train(self, trainset, devset):
        """Mathod to run Training Session.
        
        This method runs the complete training session and produces plots and
        results in every epoch.
        
        Args:
            trainset (pandas dataframe): Contains training data.
            devset (pandas dataframe): Contains validation data.

        """

        trainset = pd.read_csv(trainset)["image"].values.tolist()

        # set neural network model and loss function
        if (self.cuda):
            model = self.model.cuda()
            criterion = nn.MSELoss().cuda()
        else:
            model = self.model
            criterion = nn.MSELoss()
        
        # set optimizer
        optimizer = optim.Adam(self.model.parameters(), lr=0.0001)

        # set dataloader
        dataloader = DataLoader(dataset=Datagen(trainset, self.shape), \
                                    batch_size=self.batch_size, shuffle=True)
       
        # initialize conunter and result holder
        total_loss = []
        dev_accuracy = []
        epoch_loss = 0.0
        accuracy = 0.0

        # loop over the dataset multiple times
        for epoch in range(1, self.epochs+1):

            # initialize train loss and running loss
            batch = 0
            running_loss = 0.0
            start = timeit.default_timer()

            for image, servo, motor in dataloader:

                batch += self.batch_size

                # set input and target
                input, target = self.set_io(image, servo, motor)

                # zero the parameter gradients
                optimizer.zero_grad()

                # forward + backward + optimize
                output = model(input)
                loss = criterion(target.unsqueeze(1), output)
                loss.backward()
                optimizer.step()

                running_loss += loss.item()

                # print status for every 100 mini-batches
                if batch % 100 == 0:                    
                    stop = timeit.default_timer()
                    print('[%3d, %5d] loss: %2.7f time: %2.3f dev: %2.0f' %
                        (epoch, batch, running_loss/100, \
                                 stop-start, accuracy))

                    epoch_loss = running_loss/100
                    running_loss = 0.0
                    start = timeit.default_timer()

            # accuracy count on dev set
            accuracy = self.test(devset)
            dev_accuracy.append(accuracy)

            # total loss count
            total_loss.append(epoch_loss)
            model_path = 'models/servo_model_epoch_%d.pth' % epoch
            self.save_model(mfile=os.path.join(ODIR,model_path))
            
            # plotting loss vs epoch curve, produces log file
            self.plot_result(epoch, total_loss, dev_accuracy)
        
        #show finish message
        if self.type == "servo":
            print("Servo model training finished!")
        if self.type == "motor":
            print("Motor model training finished!")

        return None


    def test(self, testset, display=False):
        """Mathod to run Testing Session.
        
        This method runs the complete testing session producing results.
        
        Args:
            testset (pandas dataframe): Contains testing data.
            display (boolian): Flag to display result or not.
        
        Returns:
            (float): Accuracy percentage.

        """

        testset = pd.read_csv(testset)["image"].values.tolist()
        
        # set neural network model
        if (self.cuda):
            model = self.model.cuda()
        else:
            model = self.model

        # set dataloader
        dataloader = DataLoader(dataset=Datagen(testset, self.shape), \
                                    batch_size=self.batch_size, shuffle=False) 


        # initialize train loss and running loss
        total_accuracy = 0.0
        count = 0

        for image, servo, motor in dataloader:

            count += self.batch_size

            # set input and target
            input, target = self.set_io(image, servo, motor)

            # accuracy calculation
            output = model(input).round()
            accuracy = abs(target.unsqueeze(1) - output) <= 1

            total_accuracy += sum(accuracy).item()

            if display and count%100 == 0:
                print("[%5d] accuracy: %2.2f" % \
                      (count, total_accuracy*100/count))

        if display:
            print("total accuracy = %2.2f" % (total_accuracy*100/len(testset)))

        return total_accuracy*100/len(testset)


    def set_io(self, image, servo, motor):
        """Data management for Deep Learning.
        
        This method sets input and target with/without GPU support if required.
        
        Args:
            image (tensor): Tensor converted image data.
            servo (tensor): Tensor converted servo data.
            motor (tensor): Tensor converted motor data.
        
        Returns:
            input (tensor): Input in tensor form.
            target (tensor): Target in tensor form.

        """

        if (self.cuda):
            input = image.cuda(non_blocking=True)
            if self.type == "servo":
                target = servo.cuda(non_blocking=True)
            elif self.type == "motor":
                target = motor.cuda(non_blocking=True)
        else:
            input = image
            if self.type == "servo":
                target = servo
            elif self.type == "motor":
                target = motor

        return input, target


    def plot_result(self, epoch, total_loss, dev_accuracy):
        """Managing Result.
        
        This method produces result with required plots in proper format at 
        each epoch.
        
        Args:
            epoch (int): Indicator of epoch count.
            total loss (float): The accumulated loss.
            dev_accuracy (float): Accuracy percentage on validation data.

        """

        # plotting loss vs epoch curve
        plt.figure()
        plt.plot(range(1,epoch+1), total_loss, linewidth = 4)
        if self.type == "servo":
            plt.title("Servo Data Training")
            fig_path = ODIR + "/curves/Servo Loss Curve.png"
        elif self.type == "motor":
            plt.title("Motor Data Training")
            fig_path = ODIR + "/curves/Motor Loss Curve.png"

        plt.ylabel("Loss")
        plt.xlabel("Epoch")
        plt.savefig(fig_path)
        plt.close()

        # dev accuracy vs epoch curve
        plt.figure()
        plt.plot(range(1,epoch+1), dev_accuracy, linewidth = 4)
        
        if self.type == "servo":
            plt.title("Servo Data Training")
            fig_path = ODIR + "/curves/Servo Accuracy Curve.png"
        elif self.type == "motor":
            plt.title("Motor Data Training")
            fig_path = ODIR + "/curves/Motor Accuracy Curve.png"

        plt.xlabel("Epoch")
        plt.ylabel("Dev Accuracy")
        plt.savefig(fig_path)
        plt.close()
        
        # save accuracy values and show finish message
        if self.type == "servo":
            content = "{0: 4d},{1: 2.2f},\
                Servo: epoch {0: 4d} - accuracy: {1: 2.2f} - best {2: 4d}\n"\
                .format(epoch, dev_accuracy[epoch-1], np.argmax(dev_accuracy)+1)
        if self.type == "motor":
            content = "{0: 4d},{1: 2.2f},\
                Motor: epoch {0: 4d} - accuracy: {1: 2.2f} - best {2: 4d}\n"\
                .format(epoch, dev_accuracy[epoch-1], np.argmax(dev_accuracy)+1)

        # write in log
        with open(self.log, 'a') as fp:
            fp.write(content)

        return None


    def predict(self, iname):
        """Mathod for Prediction.
        
        This method predicts streering or speed value from a provided single
        image.
        
        Args:
            iname (image file): Image file as input.
        
        Returns:
            (int): Predicted steering or speed value.

        """
             
        image = self.datagen.get_image(iname)
        
        # implement GPU support if required
        if (self.cuda):
            model = self.model.cuda()
        else:
            model = self.model

        # return prediction
        if (self.cuda):
            return model(image.cuda(non_blocking=True)).round().int().item()
        else:
            return model(image).round().int().item()


    def save_model(self, mfile='models/servo_model.pth'):
        """Mathod to save Trained Model.
        
        This method predicts streering or speed value from a provided single
        image.
        
        Args:
            mfile (model file): Model file Location to save the model.

        """
        
        if self.type == "servo":
            print('Saving servo Model ')
            torch.save(self.model.state_dict(), mfile)      
        elif self.type == "motor":
            print('Saving motor Model ')
            torch.save(self.model.state_dict(), mfile)
    
        return None


    def load_model(self, mfile):
        """Mathod to load a Model.
        
        Args:
            mfile (model file): Model file Location.

        """

        # Load model from given file
        self.model.load_state_dict(torch.load(mfile, \
                                             map_location=torch.device('cpu')))

        return None


#                                                                              
# end of file
"""ANI717"""