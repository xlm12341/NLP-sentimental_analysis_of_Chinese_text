import json
data = []
with open('../../raw_data/stage3_json/2020-02-21-/2020-02-21-blog.json','r',encoding='utf-8') as f:
   data =  json.load(f)


# del data[0]

import codecs
count = 0
for i in range(len(data)):
        for j in range(len(data[i]["评论"])):
            comment_str = data[i]["评论"][j]
            file_object = codecs.open('../../raw_data/test_data/one day test/'
                                      'test.{0}.{1}.txt_utf8'.format(i + 1, j + 1), 'w', "utf-8")
            file_object.write(comment_str)
            file_object.close()
