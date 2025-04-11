import os
import time

content1 = "Как думаешь, твой ПК уже с парочкой троянов?"
content2 = "Возможно нужно просканировать систему антивирусом?."
content3 = "Или уже легче снести винду?)"

file_paths = ['HAHA.txt', 'BREDD.txt', 'STOPPPP.txt']
contents = [content1, content2, content3]

for file_path, content in zip(file_paths, contents):
    with open(file_path, 'w') as file:
        file.write(content)

def open_file(file_path):
    os.startfile(file_path)

for file in file_paths:
    open_file(file)
    time.sleep(1.7)
