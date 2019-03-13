# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# Created by: BoyuanJiang
# College of Information Science & Electronic Engineering,ZheJiang University
# Email: ginger188@gmail.com
# Copyright (c) 2017

# @Time    :17-8-27 21:25
# @FILE    :matching_networks.py
# +++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

import torch
import torch.nn as nn
import math
import numpy as np
import torch.nn.functional as F
from torch.autograd import Variable


         
class SentenceEncoder(nn.Module):
    def __init__(self, vocab_length, layer_size=64):
        super(SentenceEncoder, self).__init__()
        self.vocab_length = vocab_length
        self.layer_size = layer_size
        self.outSize = layer_size
        # Linear layer 
        self.layer1 = nn.Linear(self.vocab_length, self.layer_size)


    def oneHotEncoder(self, set):
        active_tokens_mask = (set != 1)
        #print(set)
        #print(active_tokens_mask)
        filtered = active_tokens_mask * set.type('torch.ByteTensor')

        print(set.shape)
        print("fgfg")
        set_onehot = np.zeros((int(self.vocab_length),set.shape[1]))

        for c in range(len(set[1])):
            max_pool = np.zeros((int(self.vocab_length)))
            max_pool[filtered[:,c]] = 1
            max_pool[0]=0
            set_onehot[:,c] = max_pool
        
        return set_onehot

    def encode(self, sentence_set):
        # Sentence shape= 1 x vocab_length
        sentence_set_onehot = self.oneHotEncoder(sentence_set)
        print(type(Variable(torch.from_numpy(sentence_set_onehot))))
        output = self.layer1(Variable(torch.from_numpy(sentence_set_onehot.transpose())).type('torch.FloatTensor'))
        return output
        
        
# SHOULD NOT NEED TO CHANGE
class AttentionalClassify(nn.Module):
    def __init__(self):
        super(AttentionalClassify, self).__init__()

    def forward(self, similarities, support_set_y):
        """
        Products pdfs over the support set classes for the target set image.
        :param similarities: A tensor with cosine similarites of size[batch_size,sequence_length]
        :param support_set_y:[batch_size,sequence_length,classes_num]
        :return: Softmax pdf shape[batch_size,classes_num]
        """
        softmax = nn.Softmax()
        softmax_similarities = softmax(similarities)
        preds = softmax_similarities.unsqueeze(1).bmm(support_set_y).squeeze()
        return preds

# SHOULD NOT NEED TO CHANGE, UNLESS WE WANT TO CHANGE THE DISTANCE
class DistanceNetwork(nn.Module):
    """
    This model calculates the cosine distance between each of the support set embeddings and the target image embeddings.
    """

    def __init__(self):
        super(DistanceNetwork, self).__init__()

    def forward(self, support_set, input_image):
        """
        forward implement
        :param support_set:the embeddings of the support set images.shape[sequence_length,batch_size,64]
        :param input_image: the embedding of the target image,shape[batch_size,64]
        :return:shape[batch_size,sequence_length]
        """
        eps = 1e-10
        similarities = []
        for support_image in support_set:
            sum_support = torch.sum(torch.pow(support_image, 2), 1)
            support_manitude = sum_support.clamp(eps, float("inf")).rsqrt()
            dot_product = input_image.unsqueeze(1).bmm(support_image.unsqueeze(2)).squeeze()
            cosine_similarity = dot_product * support_manitude
            similarities.append(cosine_similarity)
        similarities = torch.stack(similarities)
        return similarities.t()

# SHOULD NOT NEED TO CHANGE
class BidirectionalLSTM(nn.Module):
    def __init__(self, layer_size, batch_size, vector_dim,use_cuda):
        super(BidirectionalLSTM, self).__init__()
        """
        Initial a muti-layer Bidirectional LSTM
        :param layer_size: a list of each layer'size
        :param batch_size: 
        :param vector_dim: 
        """
        self.batch_size = batch_size
        self.hidden_size = layer_size[0]
        self.vector_dim = vector_dim
        self.num_layer = len(layer_size)
        self.use_cuda = use_cuda
        self.lstm = nn.LSTM(input_size=self.vector_dim, num_layers=self.num_layer, hidden_size=self.hidden_size,
                            bidirectional=True)
        self.hidden = self.init_hidden(self.use_cuda)

    def init_hidden(self,use_cuda):
        if use_cuda:
            return (Variable(torch.zeros(self.lstm.num_layers * 2, self.batch_size, self.lstm.hidden_size),requires_grad=False).cuda(),
                    Variable(torch.zeros(self.lstm.num_layers * 2, self.batch_size, self.lstm.hidden_size),requires_grad=False).cuda())
        else:
            return (Variable(torch.zeros(self.lstm.num_layers * 2, self.batch_size, self.lstm.hidden_size),requires_grad=False),
                    Variable(torch.zeros(self.lstm.num_layers * 2, self.batch_size, self.lstm.hidden_size),requires_grad=False))

    def repackage_hidden(self,h):
        """Wraps hidden states in new Variables, to detach them from their history."""
        if type(h) == Variable:
            return Variable(h.data)
        else:
            return tuple(self.repackage_hidden(v) for v in h)

    def forward(self, inputs):
        # self.hidden = self.init_hidden(self.use_cuda)
        #self.hidden = self.repackage_hidden(self.hidden)
        print(self.hidden)
        output, self.hidden = self.lstm(inputs, self.hidden)
        return output

class MatchingNetwork(nn.Module):
    def __init__(self, keep_prob, batch_size=32, num_channels=1, learning_rate=1e-3, fce=False, num_classes_per_set=20, \
                 num_samples_per_class=1, vocab_length=25000, use_cuda=True):
        """
        This is our main network
        :param keep_prob: dropout rate
        :param batch_size:
        :param num_channels:
        :param learning_rate:
        :param fce: Flag indicating whether to use full context embeddings(i.e. apply an LSTM on the CNN embeddings)
        :param num_classes_per_set:
        :param num_samples_per_class:
        :param image_size:
        """
        super(MatchingNetwork, self).__init__()
        self.batch_size = batch_size
        self.keep_prob = keep_prob
        # CHANGE/DELETE THIS
        self.num_channels = num_channels
        self.learning_rate = learning_rate
        self.fce = fce
        self.num_classes_per_set = num_classes_per_set
        self.num_samples_per_class = num_samples_per_class
        # CHANGE/DELETE THIS
        self.g = SentenceEncoder(vocab_length, layer_size=64)
        self.dn = DistanceNetwork()
        self.classify = AttentionalClassify()
        if self.fce:
            self.lstm = BidirectionalLSTM(layer_size=[32], batch_size=self.batch_size, vector_dim=self.g.outSize,use_cuda=use_cuda)

    def forward(self, support_set_images, support_set_y_one_hot, target_image, target_y):
        """
        Main process of the network
        :param support_set_images: shape[batch_size,sequence_length,num_channels,image_size,image_size]
        :param support_set_y_one_hot: shape[batch_size,sequence_length,num_classes_per_set]
        :param target_image: shape[batch_size,num_channels,image_size,image_size]
        :param target_y:
        :return:
        """
        # THESE PRINT STATEMENTS WERE JUST FOR ME TO CHECK 
        # THE DIMENSIONS OF THE IMAGES HERE
        #print("In MN")
        #print(support_set_images.shape)
        #print(support_set_y_one_hot.shape)
        
        # produce embeddings for support set images
        encoded_images = []
        print(support_set_images.shape)
        print("rrrrr")
        for i in np.arange(support_set_images.shape[1]):
            print(support_set_images.shape)
            print("rr111")
            sentence = support_set_images[0, i, 0, :].reshape(-1,1)
            print(sentence.shape)
            gen_encode = self.g.encode(sentence)
            encoded_images.append(gen_encode)

        # produce embeddings for target images

        target_image = self.g.encode(target_image[0].reshape(-1,1))
        encoded_images.append(target_image)
        output = torch.stack(encoded_images)

        # use fce?
        if self.fce:
            print(output.shape)
            outputs = self.lstm(output)

        # get similarities between support set embeddings and target
        similarites = self.dn(support_set=output[:-1], input_image=output[-1])

        # produce predictions for target probabilities
        preds = self.classify(similarites, support_set_y=support_set_y_one_hot)

        # calculate the accuracy
        values, indices = torch.max(preds, 0)

        #target_y_one_hot = torch.zeros(support_set_y_one_hot.shape[1], requires_grad=False)
        #target_y_one_hot[target_y] = 1

        #print(target_y_one_hot)
        accuracy = torch.mean((indices.squeeze() == target_y).float())
        #print(target_y)
        crossentropy_loss = F.cross_entropy(preds, target_y.long())

        return accuracy, crossentropy_loss