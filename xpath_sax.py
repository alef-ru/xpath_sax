import xml.sax
import hashlib
import sys
from optparse import OptionParser

class XpathElement:
	def __init__(self, name, depth):
		self.name = name
		self.children = []
		self.parent = None
		self.depth = depth
		self.content = ""

	def to_stdout(self, indentation = 0):
		printStr = str(self.depth) + ' ' + indentation*' ' + self.name
		if len(self.content) > 0:
			printStr += ' [' + self.content.strip() + ']'
		print(printStr)
		for child in self.children:
			child.to_stdout(indentation + 3)

class KleeneStar():
	pass

class Tag():
	def __init__(self, name):
		self.name = name

class Predicate():
	def __init__(self, tag, value):
		self.tag = tag
		self.value = value

class ChildRelationship():
	def __init__(self):
		self.parent = None
		self.child = None
		self.predicate = None
	def set_first(self, parent):
		self.parent = parent
	def set_second(self, child):
		self.child = child
	def set_predicate(self, predicate):
		self.predicate = predicate

class DescendantRelationship():
	def __init__(self):
		self.ancestor = None
		self.descendant = None
		self.predicate = None
	def set_first(self, ancestor):
		self.ancestor = ancestor
	def set_second(self, descendant):
		self.descendant = descendant
	def set_predicate(self, predicate):
		self.predicate = predicate

class XpathParser:
	def __init__(self):
		ret = []

	def parse(self, xpath):
		self.i = iter(xpath)
		self.j = iter(xpath[1:])
		self.next()
		self.finished = False
		tag = None
		axis = None
		current = None
		parsed = []
		while not self.finished:
			try:
				if self.char.isalnum() or self.char == '*':
					tag = self.readTag()
					parsed.append(tag)
				elif self.char == '/':
					if axis != None:
						parsed.append(axis)
						parsed.append(tag)
					axis = self.readAxis()
					axis.set_first(tag)
					tag = self.readTag()
					axis.set_second(tag)
				elif self.char == '[':
					predicate = self.readPredicate()
					axis.set_predicate(predicate)
					parsed.append(axis)
					parsed.append(tag)
					axis = None
					tag = None
			except StopIteration:
				self.finished = True
		if axis:
			parsed.append(axis)
			if tag:
				parsed.append(tag)
		return parsed


	def next(self):
		try:
			self.char = self.i.next()
		except StopIteration:
			self.finished = True
	
	def readTag(self):
		ret = []
		if self.char == '*':
			self.next()
			return KleeneStar()
		while self.char.isalnum() and not self.finished:
			ret.append(self.char)
			self.next()
		return Tag(''.join(ret))
	
	def readAxis(self):
		ret = None
		if self.char == '/':
			self.next()
			if self.char == '/':
				ret = DescendantRelationship()
				self.next()
			else:
				ret = ChildRelationship()
		return ret
	
	def readPredicate(self):
		if self.char == '[':
			self.next()
			tag = []
			while self.char != '=':
				tag.append(self.char)
				self.next()
			self.next()
			tag = ''.join(tag).strip()
			value = []
			while self.char != ']':
				value.append(self.char)
				self.next()
			self.next()
			value = ''.join(value).strip()
			ret = Predicate(Tag(tag), value)
			return ret

class XpathWeakDepth():
	def __init__(self, level):
		self.level = level
	def matches(self, depth):
		return depth >= self.level

class XpathStrictDepth():
	def __init__(self, level):
		self.level = level
	def matches(self, depth):
		return self.level == depth

class XpathPredicateDepth():
	def __init__(self, predicate, depth):
		self.predicate = predicate
		self.depth = depth
		self.satisfied = False
	def satisfy(self):
		self.satisfied = True

class XpathRetriever(xml.sax.ContentHandler):
	class SubRetriever():
		def move_backward(self):
			self.current_index -= 1
			self.current = self.xpath[self.current_index]
			if self.current_index < len(self.xpath)-1:
				self.last = False

		def move_forward(self):
			self.current_index += 1
			self.current = self.xpath[self.current_index]
			if self.current_index == len(self.xpath)-1:
				self.last = True

	def __init__(self, xpath_queries):
		xml.sax.ContentHandler.__init__(self)
		# define a retriever for each query
		self.retrievers = []
		for xpath in xpath_queries:
			r = XpathRetriever.SubRetriever()
			r.current_element = None
			r.depth = 0

			parser = XpathParser()
			r.xpath = parser.parse(xpath)
			r.raw_xpath = xpath

			# current part of query
			r.current_index = 0
			r.current = r.xpath[r.current_index]

			r.current_tag = r.current
			# stack of depths at which we are looking for tags
			r.depth_stack = [XpathStrictDepth(1)]

			# whether we are at the last part of the query
			if len(r.xpath) == 1:
				r.last = True
			else:
				r.last = False

			# whether we are going to return the tags below in the tree
			r.selecting = False

			# current predicates we need to satisfy
			r.predicates = []
			r.check_contents_for_predicate = False
			r.awaiting_predicate = []

			r.results = [] 
			self.retrievers.append(r)


	def startElement(self, name, attrs):
		for r in self.retrievers:
			r.depth += 1


			# do we need to deal with any predicates at this point?
			if len(r.predicates) > 0:
				p = r.predicates[0]
				if p.depth.matches(r.depth) and p.predicate.tag.name == name:
					r.check_contents_for_predicate = True
					r.predicate_content = ""

			# is this the tag we are looking for
			if r.current_tag and (isinstance(r.current_tag, KleeneStar) or r.current_tag.name == name) and r.depth_stack[0].matches(r.depth):
				if r.last:
					r.selecting = True
				else:
					r.move_forward()
					if isinstance(r.current, DescendantRelationship):
						if r.current.predicate:
							r.predicates.insert(0, XpathPredicateDepth(r.current.predicate, XpathWeakDepth(r.depth+2)))
						r.move_forward()
						r.current_tag = r.current
						r.depth_stack.insert(0, XpathWeakDepth(r.depth + 1))
					elif isinstance(r.current, ChildRelationship):
						if r.current.predicate:
							r.predicates.insert(0, XpathPredicateDepth(r.current.predicate, XpathStrictDepth(r.depth+2)))
						r.move_forward()
						r.current_tag = r.current
						r.depth_stack.insert(0, XpathStrictDepth(r.depth + 1))

			# select nodes
			if r.selecting:
				el = XpathElement(name, r.depth)
				if r.current_element == None:
					r.current_element = el
				elif r.selecting:
					r.current_element.children.append(el)
					el.parent = r.current_element
					r.current_element = el

	def characters(self, content):
		for r in self.retrievers:
			if r.check_contents_for_predicate:
				r.predicate_content += content

			# select node content
			if r.selecting and r.current_element:
				r.current_element.content += content

	def endElement(self, name):
		for r in self.retrievers:

			if r.check_contents_for_predicate:
				p = r.predicates[0]
				# try to satisfy predicate
				if p.predicate.value.strip() == r.predicate_content.strip():
					p.satisfy()
					r.results.extend(r.awaiting_predicate)
					r.awaiting_predicate = []
				r.check_contents_for_predicate = False
				r.predicate_content = ""

			r.depth -= 1

			# do we need to move back in our "AST"?
			if r.depth < r.depth_stack[0].level-1:
				r.move_backward()
				if isinstance(r.current, DescendantRelationship):
					r.move_backward()
					r.current_tag = r.current
					r.depth_stack.pop(0)
				elif isinstance(r.current, ChildRelationship):
					r.move_backward()
					r.current_tag = r.current
					r.depth_stack.pop(0)

			if r.selecting and r.current_element:
				# append selected results if predicates are satisfied
				if r.current_element.parent != None:
					r.current_element = r.current_element.parent
				else:
					r.selecting = False
					if len(r.predicates) > 0 and not r.predicates[0].satisfied:
						r.awaiting_predicate.append(r.current_element)
					else:
						r.results.append(r.current_element)
					r.current_element = None

			# discard useless predicates
			if len(r.predicates) > 0:
				p = r.predicates[0]
				# if we are below predicate level, drop the predicate
				if r.depth < p.depth.level-2:
					r.predicates.pop(0)
				# if we are at predicate level, mark it as unsatisfied
				elif r.depth < p.depth.level-1:
					p.satisfied = False 			
					r.awaiting_predicate = []

def xpath_sax(handle, queries):
	if isinstance(queries, str):
		query = queries
		retriever = XpathRetriever([query])
		xml.sax.parse(handle, retriever)
		return retriever.retrievers[0].results
	elif isinstance(queries, list):
		retriever = XpathRetriever(queries)
		xml.sax.parse(handle, retriever)
		ret = []
		for r in retriever.retrievers:
			ret.append(r.results)
		return ret
	elif isinstance(queries, dict):
		indexed_keys = {}
		queries_real = []
		i = 0
		for key, query in queries.iteritems():
			indexed_keys[i] = key
			queries_real.append(query)
			i += 1
		retriever = XpathRetriever(queries_real)
		xml.sax.parse(handle, retriever)
		ret = {}
		for i, r in enumerate(retriever.retrievers):
			ret[indexed_keys[i]] = r.results
		return ret
	else:
		raise RuntimeError("Query argument must be one of str, list or dict.")
	
def main():
	usage = "usage: %prog xml_file query"
	parser = OptionParser(usage=usage)
	(options, args) = parser.parse_args()
	if len(args) < 2:
		print "Try -h for usage."
		sys.exit(1)

	xml_filename = args[0]
	query = ' '.join(args[1:])
	print("--- {} ---".format(query))

	results = xpath_sax(open(xml_filename), query)
	for result in results:
		result.to_stdout()
		print("---------")

if __name__ == "__main__":
	main()
