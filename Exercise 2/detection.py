import os

import cv2
import numpy as np

from contour import get_contour, compare_contours
from rotation import find_rotation_angle_hough, rotate_image


class KnownLetter:
    def __init__(self, name, contour):
        self.name = name
        self.contour = contour


class Letter:
    def __init__(self, x1, x2, y1, y2, contour=None):
        self.x1 = x1
        self.x2 = x2
        self.y1 = y1
        self.y2 = y2
        self.coordinates = ((x1, y1), (x2, y2))
        self.contour = contour
        self.looks_like = None


class Word:
    def __init__(self, x1, x2, y1, y2, letters=None):
        self.x1 = x1
        self.x2 = x2
        self.y1 = y1
        self.y2 = y2
        self.coordinates = ((x1, y1), (x2, y2))
        self.letters = letters


class Line:
    def __init__(self, y1, y2, words=None):
        self.y1 = y1
        self.y2 = y2
        self.coordinates = (y1, y2)
        self.words = words


def get_line_indices(image):
    image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    image = cv2.GaussianBlur(image, (25, 25), 0)

    _, binarizedImage = cv2.threshold(image, 200, 255, cv2.THRESH_BINARY)

    vertical_projection = np.sum(binarizedImage, axis=1)
    vertical_projection[vertical_projection < np.max(vertical_projection)] = 0
    vertical_projection[vertical_projection > 0] = 255

    lines = []
    start_index = None
    for i, val in enumerate(vertical_projection):
        if val == 0 and start_index is None:
            start_index = i
        elif val == 255 and start_index is not None:
            lines.append(Line(start_index, i - 1))
            start_index = None

    if start_index is not None:
        lines.append(Line(start_index, len(vertical_projection) - 1))

    return lines


def get_words(image, lines):
    for line in lines:
        line_image = image[line.y1:line.y2, :]
        line_image = cv2.cvtColor(line_image, cv2.COLOR_BGR2GRAY)
        line_image = cv2.GaussianBlur(line_image, (35, 41), 0)

        _, binarizedImage = cv2.threshold(line_image, 252, 255, cv2.THRESH_BINARY)

        horizontal_projection = np.sum(binarizedImage, axis=0)
        horizontal_projection[horizontal_projection < np.max(horizontal_projection)] = 0
        horizontal_projection[horizontal_projection > 0] = 255

        words = []
        start_index = None
        for i, val in enumerate(horizontal_projection):
            if val == 0 and start_index is None:
                start_index = i
            elif val == 255 and start_index is not None:
                words.append(Word(start_index, i - 1, line.y1, line.y2))
                start_index = None

        if start_index is not None:
            words.append(Word(start_index, len(horizontal_projection) - 1, line.y1, line.y2))

        line.words = words

    return lines


def get_letters(image, lines):
    for line in lines:
        for word in line.words:
            word_image = image[word.y1:word.y2, word.x1:word.x2]
            word_image = cv2.cvtColor(word_image, cv2.COLOR_BGR2GRAY)

            _, binarizedImage = cv2.threshold(word_image, 238, 255, cv2.THRESH_BINARY)

            horizontal_projection = np.sum(binarizedImage, axis=0)
            horizontal_projection[horizontal_projection < np.max(horizontal_projection)] = 0
            horizontal_projection[horizontal_projection > 0] = 255

            letters = []
            start_index = None
            for i, val in enumerate(horizontal_projection):
                if val == 0 and start_index is None:
                    start_index = i
                elif val == 255 and start_index is not None:
                    if word.x1 + start_index != word.x1 + i - 1:
                        letters.append(Letter(word.x1 + start_index, word.x1 + i - 1, word.y1, word.y2))
                    start_index = None

            if start_index is not None and (word.x1 + start_index != word.x1 + len(horizontal_projection) - 1):
                letters.append(
                    Letter(word.x1 + start_index, word.x1 + len(horizontal_projection) - 1, word.y1, word.y2))

            word.letters = letters

    return lines


def generate_known_letters():
    current_directory = os.getcwd()
    final_directory = os.path.join(current_directory, r'letters')
    if not os.path.exists(final_directory):
        os.makedirs(final_directory)
    letters = cv2.imread('letters.png')
    if letters is None:
        print('Could not find letters.png')
        return
    letter_lines = get_line_indices(letters)
    letter_lines = get_words(letters, letter_lines)
    letter_lines = get_letters(letters, letter_lines)

    # ASCII value for 'a'
    name = 97
    for letter_line in letter_lines:
        for letter_word in letter_line.words:
            for letter_letter in letter_word.letters:
                letter_img = letters[letter_letter.y1:letter_letter.y2, letter_letter.x1:letter_letter.x2]
                cv2.imwrite('letters/' + chr(name) + '.png', letter_img)
                name += 1

    known_letter_names = [chr(i) for i in range(97, 123)]
    known_letters = []
    for known_letter_name in known_letter_names:
        known_letter_img = cv2.imread('letters/' + known_letter_name + '.png')
        known_letter_img = cv2.cvtColor(known_letter_img, cv2.COLOR_BGR2GRAY)
        known_letter_contour = get_contour(known_letter_img.astype(np.uint8))
        known_letters.append(KnownLetter(known_letter_name, known_letter_contour))

    return known_letters


if __name__ == '__main__':
    known_letters = generate_known_letters()
    img = cv2.imread('letters.png')
    if img is None:
        print("Letters.png needs to be in this folder!")
        exit(1)
    angle = find_rotation_angle_hough(img)
    img = rotate_image(img, -angle)
    lines = get_line_indices(img)
    lines = get_words(img, lines)
    lines = get_letters(img, lines)

    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    string = ''
    for line in lines:
        for word in line.words:
            for letter in word.letters:
                letter_img = img[letter.y1:letter.y2, letter.x1:letter.x2]
                letter.contour = get_contour(letter_img.astype(np.uint8))
                best_score = np.inf
                for known_letter in known_letters:
                    score = compare_contours(letter.contour, known_letter.contour)
                    if score < best_score:
                        best_score = score
                        letter.looks_like = known_letter
                if best_score == np.inf:
                    letter.looks_like = KnownLetter('?', None)

                string += letter.looks_like.name
            string += ' '
        string += '\n'

    print(string)
    print('Done')
