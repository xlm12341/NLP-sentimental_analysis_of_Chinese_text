
import os
import xlwt
import pickle
import itertools
import nltk
import os
import sklearn
import numpy as np
import matplotlib.pyplot as plt
from sklearn import svm, datasets
from sklearn.metrics import roc_curve, auc
from nltk.collocations import BigramCollocationFinder
from nltk.metrics import BigramAssocMeasures
from nltk.probability import FreqDist, ConditionalFreqDist
from nltk.classify.scikitlearn import SklearnClassifier
from sklearn.model_selection import StratifiedKFold
from sklearn.svm import SVC, LinearSVC, NuSVC
from sklearn.naive_bayes import MultinomialNB, BernoulliNB
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score,precision_score,recall_score,f1_score


# pos_f = '../pkl_data/tagged_data/pos_review.pkl'
# neg_f = '../pkl_data/tagged_data/neg_review.pkl'

pos_f = '../pkl_data/tagged_data/pos_comment.pkl'
neg_f = '../pkl_data/tagged_data/neg_comment.pkl'

pos_f = '../pkl_data/tagged_data/pos_comment_oneday.pkl'
neg_f = '../pkl_data/tagged_data/neg_comment_oneday.pkl'
# 1 提取特征方法
# 1.1 把所有词作为特征
def bag_of_words(words):
    return dict([(word, True) for word in words])


# 1.2 把双词搭配（bigrams）作为特征
def bigram(words, score_fn=BigramAssocMeasures.pmi, n=1000):

    bigram_finder = BigramCollocationFinder.from_words(words)  # 把文本变成双词搭配的形式
    # print(bigram_finder)
    bigrams = bigram_finder.nbest(score_fn, n)  # 使用了卡方统计的方法，选择排名前1000的双词,不一定有1000个

    return bag_of_words(bigrams)


# 1.3 把所有词和双词搭配一起作为特征
def bigram_words(words, score_fn=BigramAssocMeasures.pmi, n=1000):

    tuple_words = []
    for i in words:
        temp = (i,)
        tuple_words.append(temp)

    bigram_finder = BigramCollocationFinder.from_words(words)
    bigrams = bigram_finder.nbest(score_fn, n) # 使用了卡方统计的方法，选择排名前1000的双词

    return bag_of_words(tuple_words + bigrams)  # 所有词和（信息量大的）双词搭配一起作为特征


# 2 特征选择方法
# 2.1 计算出整个语料里面每个词的信息量
# 2.1.1 计算整个语料里面每个词的信息量
def create_word_scores():
    posWords = pickle.load(open(pos_f, 'rb'))
    negWords = pickle.load(open(neg_f, 'rb'))

    posWords = list(itertools.chain(*posWords))  # 把多维数组解链成一维数组
    negWords = list(itertools.chain(*negWords))  # 同理

    word_fd = FreqDist()  # 可统计所有词的词频
    cond_word_fd = ConditionalFreqDist()  # 可统计积极文本中的词频和消极文本中的词频
    for word in posWords:
        word_fd[word] += 1
        cond_word_fd["pos"][word] += 1
    for word in negWords:
        word_fd[word] += 1
        cond_word_fd["neg"][word] += 1

    pos_word_count = cond_word_fd['pos'].N()  # 积极词的数量
    neg_word_count = cond_word_fd['neg'].N()  # 消极词的数量
    total_word_count = pos_word_count + neg_word_count

    word_scores = {}
    for word, freq in word_fd.items():
        pos_score = BigramAssocMeasures.chi_sq(cond_word_fd['pos'][word], (freq, pos_word_count),
                                               total_word_count)  # 计算积极词的卡方统计量，这里也可以计算互信息等其它统计量
        neg_score = BigramAssocMeasures.chi_sq(cond_word_fd['neg'][word], (freq, neg_word_count),
                                               total_word_count)  # 同理
        word_scores[word] = pos_score + neg_score  # 一个词的信息量等于积极卡方统计量加上消极卡方统计量

    return word_scores  # 包括了每个词和这个词的信息量


# 2.1.2 计算整个语料里面每个词和双词搭配的信息量
def create_word_bigram_scores():
    posdata = pickle.load(open(pos_f, 'rb'))
    negdata = pickle.load(open(neg_f, 'rb'))

    posWords = list(itertools.chain(*posdata))
    negWords = list(itertools.chain(*negdata))

    bigram_finder = BigramCollocationFinder.from_words(posWords)
    posBigrams = bigram_finder.nbest(BigramAssocMeasures.chi_sq, 5000)
    bigram_finder = BigramCollocationFinder.from_words(negWords)
    negBigrams = bigram_finder.nbest(BigramAssocMeasures.chi_sq, 5000)

    pos = posWords + posBigrams  # 词和双词搭配
    neg = negWords + negBigrams

    word_fd = FreqDist()
    cond_word_fd = ConditionalFreqDist()
    for word in pos:
        word_fd[word] += 1
        cond_word_fd["pos"][word] += 1
    for word in neg:
        word_fd[word] += 1
        cond_word_fd["neg"][word] += 1

    pos_word_count = cond_word_fd['pos'].N()
    neg_word_count = cond_word_fd['neg'].N()
    total_word_count = pos_word_count + neg_word_count

    word_scores = {}
    for word, freq in word_fd.items():
        pos_score = BigramAssocMeasures.chi_sq(cond_word_fd['pos'][word], (freq, pos_word_count), total_word_count)  # 计算积极词的卡方统计量，这里也可以计算互信息等其它统计量
        neg_score = BigramAssocMeasures.chi_sq(cond_word_fd['neg'][word], (freq, neg_word_count), total_word_count)
        word_scores[word] = pos_score + neg_score

    return word_scores


# 2.2 根据信息量进行倒序排序（Reverse==True）0，选择排名靠前的信息量的词
def find_best_words(word_scores, number):
    best_vals = sorted(word_scores.items(), key=lambda w_s: w_s[1], reverse=True)[:number]  # 把词按信息量倒序排序。number是特征的维度，是可以不断调整直至最优的
    best_words = set([w for w, s in best_vals])
    return best_words


# 2.3 把选出的这些词作为特征（这就是选择了信息量丰富的特征）提取信息量丰富的特征
def best_word_features(words):
    # load_data()
    # word_scores = create_word_bigram_scores()
    global best_words
    # best_words = find_best_words(word_scores, 7500)
    return dict([(word, True) for word in words if word in best_words])


pos_review = []  # 积极数据
neg_review = []  # 消极数据


# 3 分割数据及赋予类标签
# 3.1 载入数据
def load_data():
    global pos_review, neg_review
    pos_review = pickle.load(open(pos_f, 'rb'))
    neg_review = pickle.load(open(neg_f, 'rb'))


# 3.2 使积极文本的数量和消极文本的数量一样 (跳过)

# 3.3 赋予类标签
# 3.3.1 积极
def pos_features(feature_extraction_method):
    posFeatures = []
    for i in pos_review:
        posWords = [feature_extraction_method(i), 'pos']  # 为积极文本赋予"pos"
        posFeatures.append(posWords)
    return posFeatures  # 列表里的元素数量和pos_review里的一样多


# 3.3.2 消极
def neg_features(feature_extraction_method):

    negFeatures = []
    for j in neg_review:
        negWords = [feature_extraction_method(j), 'neg']  # 为消极文本赋予"neg"
        negFeatures.append(negWords)
    return negFeatures


train = []  # 训练集
devtest = []  # 开发测试集
test = []  # 测试集
dev = []
dev_roc = []
tag_dev_roc = []
tag_dev = []
for_roc_plot = []

# 3.4 把特征化之后的数据分割为开发集和测试集//训练集和开发测试集
def cut_data(posFeatures, negFeatures):
    global train, devtest, test, for_roc_plot
    # train = posFeatures[300:] + negFeatures[300:]
    # devtest = posFeatures[300:500] + negFeatures[300:500]
    # test_data = posFeatures[:500] + negFeatures[:500]
    train = posFeatures[250:] + negFeatures[250:]  # 后800条作训练
    devtest = posFeatures[:250] + negFeatures[:250]  # 前200条作开发测试
    for_roc_plot = posFeatures[:] + negFeatures[:]
    # 这里采用了手动分类，实际上不科学，应该调包KFold，GroupKFold，StratifiedKFold

# 4.1 开发测试集分割人工标注的标签和数据
def cut_devtest():
    global dev, tag_dev, dev_roc, tag_dev_roc
    dev, tag_dev = zip(*devtest)
    dev_roc, tag_dev_roc = zip(*for_roc_plot)

# 4.2 使用训练集训练分类器
# 4.3 用分类器对开发测试集里面的数据进行分类，给出分类预测的标签
# 4.4 对比分类标签和人工标注的差异，计算出准确度
# i = 0
def score(classifier):
    classifier = nltk.SklearnClassifier(classifier)  # 在nltk 中使用scikit-learn的接口
    classifier.train(train)  # 训练分类器

    pred = classifier.classify_many(dev)  # 对开发测试集的数据进行分类，给出预测的标签
    a_s = accuracy_score(tag_dev, pred)
    p_s = precision_score(tag_dev, pred, average='binary', pos_label="pos")
    r_s = recall_score(tag_dev, pred, average='binary', pos_label="pos")
    f1_s = f1_score(tag_dev, pred, average='binary', pos_label="pos")
    return a_s, p_s, r_s, f1_s  # 对比分类预测结果和人工标注的正确结果，给出分类器准确度

def plot_ROC(classifier):
    cv = StratifiedKFold(n_splits=6)  # 导入该模型，后面将数据划分6份
    classifier = SklearnClassifier(classifier)
    global k
    # 画平均ROC曲线的两个参数
    mean_tpr = 0.0  # 用来记录画平均ROC曲线的信息
    mean_fpr = np.linspace(0, 1, 100)
    cnt = 0

    for i, (train, test) in enumerate(cv.split(dev_roc, tag_dev_roc)):  # 利用模型划分数据集和目标变量 为一一对应的下标
        cnt += 1
        devtest1 = np.array(for_roc_plot)
        classifier.train(devtest1[train])
        # print(cnt)
        # print(train)

        dev1 = np.array(dev_roc)
        tag_dev1 = np.array(tag_dev_roc)
        pred_ = classifier.prob_classify_many(dev1[test]) # 测试集的概率
        # print(pred_)
        # probas_ = classifier.fit(dev1[train], tag_dev1[train]).predict_proba(dev1[test])  # 训练模型后预测每条样本得到两种结果的概率
        probas_ = []
        for j in pred_:
            probas_.append(j.prob('pos'))
        fpr, tpr, thresholds = roc_curve(tag_dev1[test], probas_, pos_label='pos')  # 该函数得到伪正例、真正例、阈值，这里只使用前两个
        # print(fpr)
        mean_tpr += np.interp(mean_fpr, fpr, tpr)  # 插值函数 interp(x坐标,每次x增加距离,y坐标)  累计每次循环的总值后面求平均值
        mean_tpr[0] = 0.0  # 将第一个真正例=0 以0为起点

        roc_auc = auc(fpr, tpr)  # 求auc面积
        plt.plot(fpr, tpr, lw=1, label='ROC fold {0:.2f} (area = {1:.2f})'.format(i, roc_auc))  # 画出当前分割数据的ROC曲线

    plt.plot([0, 1], [0, 1], '--', color=(0.6, 0.6, 0.6), label='Luck')  # 画对角线

    mean_tpr /= cnt  # 求数组的平均值
    mean_tpr[-1] = 1.0  # 坐标最后一个点为（1,1）  以1为终点
    mean_auc = auc(mean_fpr, mean_tpr)

    plt.plot(mean_fpr, mean_tpr, 'k--', label='Mean ROC (area = {0:.2f})'.format(mean_auc), lw=2)

    plt.xlim([-0.05, 1.05])  # 设置x、y轴的上下限，设置宽一点，以免和边缘重合，可以更好的观察图像的整体
    plt.ylim([-0.05, 1.05])
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')  # 可以使用中文，但需要导入一些库即字体
    plt.title('Receiver operating characteristic curve using {0}'.format(classifier))
    plt.legend(loc="lower right")
    fig = plt.gcf()
    plt.show()
    fig.savefig('../out/ROC_curves/第{0}张'.format(k+1), dpi=400)    #保存图片
    k = k+1
def try_diffirent_classifiers():

    results = list()
    results.append(score(BernoulliNB()))
    plot_ROC(BernoulliNB())
    results.append(score(MultinomialNB()))
    plot_ROC(MultinomialNB())
    results.append(score(LogisticRegression(max_iter=10000)))
    plot_ROC(LogisticRegression(max_iter=10000))
    results.append(score(SVC()))
    # plot_ROC(SVC)
    results.append(score(LinearSVC(max_iter=10000)))
    # plot_ROC(LinearSVC(max_iter=10000))
    results.append(score(NuSVC()))
    # plot_ROC(NuSVC())

    return results


best_words = []
classifiers = ['BernoulliNB', 'MultinomiaNB', 'LogisticRegression', 'SVC', 'LinearSVC', 'NuSVC']
k = 0 # 统计有几张roc曲线图
# 4.5 检验不同分类器和不同的特征选择的结果
def compare_test():

    global pos_review, neg_review


    load_data()

    # 创建 xls 文件对象
    wb = xlwt.Workbook()
    # 新增一个表单
    sh = wb.add_sheet('compare')
    col_cnt = 0

    # 使用所有词作为特征
    posFeatures = pos_features(bag_of_words)
    negFeatures = neg_features(bag_of_words)

    cut_data(posFeatures, negFeatures)
    cut_devtest()
    # print(train)
    sh.write(0, 0, '所有词')
    sh.write(0, 1, 'accuracy')
    sh.write(0, 2, 'precision_score')
    sh.write(0, 3, 'recall_score')
    sh.write(0, 4, 'f1_score')
    col_cnt += 1
    results = try_diffirent_classifiers()
    temp = 0
    for i in classifiers:
        sh.write(col_cnt, 0, i)
        sh.write(col_cnt, 1, results[temp][0])
        sh.write(col_cnt, 2, results[temp][1])
        sh.write(col_cnt, 3, results[temp][2])
        sh.write(col_cnt, 4, results[temp][3])

        col_cnt += 1
        temp += 1

    # 使用双词搭配作为特征
    posFeatures = pos_features(bigram)
    negFeatures = neg_features(bigram)

    cut_data(posFeatures, negFeatures)
    cut_devtest()

    col_cnt += 1
    sh.write(col_cnt, 0, '双词搭配')
    col_cnt += 1
    results = try_diffirent_classifiers()
    temp = 0
    for i in classifiers:
        sh.write(col_cnt, 0, i)
        sh.write(col_cnt, 1, results[temp][0])
        sh.write(col_cnt, 2, results[temp][1])
        sh.write(col_cnt, 3, results[temp][2])
        sh.write(col_cnt, 4, results[temp][3])
        col_cnt += 1
        temp += 1

    # 使用所有词加上双词搭配作为特征
    posFeatures = pos_features(bigram_words)
    negFeatures = neg_features(bigram_words)

    cut_data(posFeatures, negFeatures)
    cut_devtest()

    col_cnt += 1
    sh.write(col_cnt, 0, '所有词和双词搭配')
    col_cnt += 1
    results = try_diffirent_classifiers()
    temp = 0
    for i in classifiers:
        sh.write(col_cnt, 0, i)
        sh.write(col_cnt, 1, results[temp][0])
        sh.write(col_cnt, 2, results[temp][1])
        sh.write(col_cnt, 3, results[temp][2])
        sh.write(col_cnt, 4, results[temp][3])
        col_cnt += 1
        temp += 1

    dimension = [100,200,300,400,500,1000,1500,2000,2500,3000]

    row_cnt = 0
    col_cnt += 1
    sh.write(col_cnt, row_cnt, '信息量丰富的所有词')
    row_cnt += 1
    col_cnt += 1

    temp = 0
    temp_col = col_cnt
    for i in classifiers:
        col_cnt += 1
        sh.write(col_cnt, 0, i)
        temp += 1

    # 计算信息量丰富的词，并以此作为分类特征
    word_scores = create_word_scores()
    for d in dimension:
        col_cnt = temp_col
        sh.write(col_cnt, row_cnt, d)
        col_cnt += 1

        global best_words
        best_words = find_best_words(word_scores, int(d))  # 选择信息量最丰富的d个的特征

        posFeatures = pos_features(best_word_features)
        negFeatures = neg_features(best_word_features)

        cut_data(posFeatures, negFeatures)
        cut_devtest()

        results = try_diffirent_classifiers()
        temp = 0
        for i in classifiers:
            sh.write(col_cnt, row_cnt, results[temp][0])
            col_cnt += 1
            temp += 1
        row_cnt += 1

    row_cnt = 0
    col_cnt += 1
    sh.write(col_cnt, row_cnt, '信息量丰富的所有词和双词搭配')
    row_cnt += 1
    col_cnt += 1

    temp = 0
    temp_col = col_cnt
    for i in classifiers:
        col_cnt += 1
        sh.write(col_cnt, 0, i)
        temp += 1

    # 计算信息量丰富的词，并以此作为分类特征
    word_scores = create_word_bigram_scores()
    for d in dimension:
        col_cnt = temp_col
        sh.write(col_cnt, row_cnt, d)
        col_cnt += 1

        best_words = find_best_words(word_scores, int(d))  # 选择信息量最丰富的d个的特征

        posFeatures = pos_features(best_word_features)
        negFeatures = neg_features(best_word_features)

        cut_data(posFeatures, negFeatures)
        cut_devtest()

        results = try_diffirent_classifiers()
        temp = 0
        for i in classifiers:
            sh.write(col_cnt, row_cnt, results[temp][0])
            col_cnt += 1
            temp += 1
        row_cnt += 1

    # 保存文件
    if(os.path.exists('../out/compare.xls')):
        os.remove('../out/compare.xls')
    wb.save('../out/compare.xls')
    # word_scores_1 = create_word_scores()
    # word_scores_2 = create_word_bigram_scores()
    # best_words_1 = find_best_words(word_scores_1, 5000)
    # best_words_2 = find_best_words(word_scores_2, 5000)
    # load_data()
    # posFeatures = pos_features(best_word_features, best_words_2)  # 使用所有词作为特征
    # negFeatures = neg_features(best_word_features, best_words_2)
    # cut_data(posFeatures, negFeatures)
    # cut_devtest()
    # # posFeatures = pos_features(bigram)
    # # negFeatures = neg_features(bigram)
    #
    # # posFeatures = pos_features(bigram_words)
    # # negFeatures = neg_features(bigram_words)
    #
    # print('BernoulliNB`s accuracy is %f' % score(BernoulliNB()))
    # print('MultinomiaNB`s accuracy is %f' % score(MultinomialNB()))
    # print('LogisticRegression`s accuracy is %f' % score(LogisticRegression()))
    # print('SVC`s accuracy is %f' % score(SVC()))
    # print('LinearSVC`s accuracy is %f' % score(LinearSVC()))
    # print('NuSVC`s accuracy is %f' % score(NuSVC()))


# 5.1 使用测试集测试分类器的最终效果
# 这个函数没用到，可以暂时不管
def use_the_best():
    word_scores = create_word_bigram_scores()  # 使用词和双词搭配作为特征
    best_words = find_best_words(word_scores, 4000)  # 特征维度1500
    load_data()
    posFeatures = pos_features(best_word_features, best_words)
    negFeatures = neg_features(best_word_features, best_words)
    cut_data(posFeatures, negFeatures)
    trainSet = posFeatures[1500:] + negFeatures[1500:]  # 使用了更多数据
    testSet = posFeatures[:500] + negFeatures[:500]
    test, tag_test = zip(*testSet)


    # 5.2 存储分类器
    def final_score(classifier):
        classifier = SklearnClassifier(classifier)
        classifier.train(trainSet)
        pred = classifier.classify_many(test)
        return accuracy_score(tag_test, pred)

    print(final_score(MultinomialNB()))  #使用开发集中得出的最佳分类器


# 5.3 把分类器存储下来（存储分类器和前面没有区别，只是使用了更多的训练数据以便分类器更为准确）
def store_classifier():
    load_data()
    word_scores = create_word_bigram_scores()
    global best_words
    best_words = find_best_words(word_scores, 2500) # 根据compare的表格选取最合适的维度

    posFeatures = pos_features(best_word_features)
    negFeatures = neg_features(best_word_features)

    trainSet = posFeatures + negFeatures

    MultinomialNB_classifier = SklearnClassifier(MultinomialNB()) #根据compare的表格选取最合适的分类器
    MultinomialNB_classifier.train(trainSet)
    pickle.dump(MultinomialNB_classifier, open('../out/classifier.pkl', 'wb'))


# 6 使用分类器进行分类，并给出概率值
# 6.1 把文本变为特征表示的形式
def transfer_text_to_moto():

    moto = pickle.load(open('../pkl_data/test_data/test_review.pkl', 'rb'))  # 载入文本数据

    def extract_features(data):
        feat = []   #列表里的元素是包含每一条评论的特征词的字典
        for i in data:
            feat.append(best_word_features(i))
        return feat

    moto_features = extract_features(moto)  # 把文本转化为特征表示的形式
    return moto_features


# 6.2 对文本进行分类，给出概率值
def application(moto_features):
    clf = pickle.load(open('../out/classifier.pkl', 'rb'))  # 载入分类器

    pred = clf.prob_classify_many(moto_features)  # 该方法是计算分类概率值的
    print(pred)
    p_file = open('../out/test_result.txt', 'w')  # 把结果写入文档
    for i in pred:
        p_file.write(str(i.prob('pos')) + ' ' + str(i.prob('neg')) + '\n')
    p_file.close()


if __name__ == '__main__':
    # store_classifier()
    # moto_features = transfer_text_to_moto()
    # application(moto_features)
    compare_test()


