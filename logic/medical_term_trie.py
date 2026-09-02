import re
import logging

from DAL import get_dal

logger = logging.getLogger("clearmed.medical_term_trie")

def normalize_text(text):
	# normalizes text so that searching is consistent
	# e.g.:
	# 'HbA1C,'  -> 'hba1c'
	# 'Type-2 Diabetes' -> 'type 2 diabetes'
	# convert to lowercase
	text = text.lower()
	# remove punctuation
	text = re.sub(r"[^a-z0-9\s]", " ", text)
	# normalize whitespace
	text = re.sub(r"\s+", " ", text).strip()
	return text

def tokenize(text):
	# splits text into a list of words
	return normalize_text(text).split()

class TrieNode:
	# each node in the tree represents one word
	# e.g.:
	# type -> 2 -> diabetes
	def __init__(self):
		# dict: word -> next TrieNode
		self.children = {}
		# is this the end of a valid term?
		self.is_end = False
		# if this is the end of a term: what is the main term?
		# e.g. HbA1C -> main_term = A1C
		self.main_term = None

class MedicalTermTrie:
	def __init__(self):
		# root is the start of the whole tree
		self.root = TrieNode()

	def insert_words(self, words, main_term):
		# inserts an already-tokenized/normalized phrase into the tree
		# words: ['type', '2', 'diabetes']
		# main_term: 'Type 2 Diabetes'
		# if phrase is empty
		if not words:
			return
		# start from the root
		current = self.root
		# go word by word
		for word in words:
			# if this child doesn't exist yet, create a new node
			if word not in current.children:
				current.children[word] = TrieNode()
			# go down a level in the tree
			current = current.children[word]
		# mark this as the end of a term
		current.is_end = True
		# store the main medical term
		current.main_term = main_term

	def find_word_matches(self, words):
		# receives an already-tokenized/normalized word list and returns
		# which medical terms were found, as word-index ranges. Callers
		# (language-specific detectors) map these back to character offsets
		# in their own raw text.
		found_terms = []
		# i = where we start searching in the text
		i = 0
		while i < len(words):
			# start each search over from the root
			current = self.root
			# keep the longest match we found
			longest_match = None
			# how far the match reached
			longest_match_end = i
			# j advances forward in the text
			j = i
			# try to advance in the tree as long as the next word exists as a child
			while j < len(words) and words[j] in current.children:
				# go down to the next depth in the tree
				current = current.children[words[j]]
				# if we reached the end of a valid term, save it
				if current.is_end:
					longest_match = {
						# the main term in the database
						"main_term": current.main_term,
						# where it started in the text
						"start_word_index": i,
						# where it ended in the text
						"end_word_index": j
					}
					longest_match_end = j
				# keep checking for a longer term
				j += 1
			# if we found a match, take the longest one
			if longest_match:
				found_terms.append(longest_match)
				# skip forward to avoid detecting overlapping terms
				i = longest_match_end + 1
			else:
				# if no term was found, advance one word
				i += 1
		logger.debug(f"Found {len(found_terms)} term match(es) in text")
		return found_terms

def load_terms_from_db():
	# loads all the terms from the DB via the DAL
	dal = get_dal()
	return dal.get_all_terms()

def build_trie_from_db():
	# builds a trie from all the medical terms
	trie = MedicalTermTrie()
	rows = load_terms_from_db()
	for row in rows:
		term = row["term"]
		synonyms = row["synonyms"]
		# insert the main term
		trie.insert_words(tokenize(term), term)
		# also insert synonyms
		for synonym in synonyms:
			trie.insert_words(tokenize(synonym), term)
	logger.info(f"Built trie from {len(rows)} term(s) in the database")
	return trie
