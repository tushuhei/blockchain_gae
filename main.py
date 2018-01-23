# coding: utf-8
from flask import Flask, render_template, request, redirect, jsonify
from google.appengine.ext import ndb
from google.appengine.api import users
from google.appengine.api import memcache
import logging
import hashlib
import json
from json import JSONEncoder
import functools

app = Flask(__name__)

class Transaction(ndb.Model):
  sender = ndb.StringProperty()
  recipient = ndb.StringProperty()
  amount = ndb.IntegerProperty()

  def to_serializable(self):
    return {
        'sender': self.sender,
        'recipient': self.recipient,
        'amount': self.amount,
    }

class Block(ndb.Model, JSONEncoder):
  index = ndb.IntegerProperty()
  timestamp = ndb.DateTimeProperty(auto_now_add=True)
  transactions = ndb.LocalStructuredProperty(Transaction, repeated=True)
  proof = ndb.StringProperty()
  previous_hash = ndb.StringProperty()

  def to_serializable(self):
    return {
        'index': self.index,
        'timestamp': str(self.timestamp),
        'transactions': [t.to_serializable() for t in self.transactions],
        'proof': self.proof,
        'previous_hash': self.previous_hash,
    }

class Node(ndb.Model):

  def calc_coin(self):
    all_transactions = [t for b in self.chain for t in b.transactions]
    all_transactions += self.current_transactions
    coin_in = sum([
      t.amount for t in all_transactions if t.recipient == self.key.id()])
    coin_out = sum([
      t.amount for t in all_transactions if t.sender == self.key.id()])
    return coin_in - coin_out

  chain = ndb.LocalStructuredProperty(Block, repeated=True)
  current_transactions = ndb.LocalStructuredProperty(Transaction, repeated=True)
  neighbor_nodes = ndb.StringProperty(repeated=True)
  coins = ndb.ComputedProperty(calc_coin)

  def to_serializable(self):
    return {
        'chain': [block.to_serializable() for block in self.chain],
        'current_transactions': [
          t.to_serializable() for t in self.current_transactions],
        'neighbor_nodes': list(set(self.neighbor_nodes)),
        'coins': self.coins,
    }

  def new_block(self, proof, previous_hash=None):
    """
    Creates a new Block in the Blockchain.

    :param proof: <int> The proof given by the Proof of Work algorithm
    :param previous_hash: (Optional) <str> Hash of previous Block
    :return: <dict> New Block
    """
    block = Block(
      index=len(self.chain) + 1,
      transactions=self.current_transactions,
      proof=proof,
      previous_hash=previous_hash or self.hash(self.chain[-1]),
    )

    # Reset the current list of transactions.
    self.current_transactions = []
    self.chain.append(block)
    self.put()
    return block


  def new_transaction(self, sender, recipient, amount):
    """
    Creates a new transaction to go into the next mined Block.

    :param sender: <str> Address of the Sender
    :param recipient: <str> Address of the Recipient
    :param amount: <int> Amount
    :return: <int> The index of the Block that will hold this transaction
    """

    transaction = Transaction(
        sender=sender,
        recipient=recipient,
        amount=amount)
    self.current_transactions.append(transaction)
    return self.chain[-1].index + 1


  @staticmethod
  def hash(block):
    """Creates a SHA-256 hash of a Block

    :param block: <dict> Block
    :return: <str>
    """

    block_string = json.dumps(block.to_serializable()).encode()
    return hashlib.sha256(block_string).hexdigest()


  @staticmethod
  def valid_proof(last_proof, proof):
    """
    Validates the Proof: Does hash (last_proof, proof) contains 4 leading zeros?

    :param last_proof: <int> Previous Proof
    :param proof: <int> Current Proof
    :return: <bool> Whether the Proof is validated.
    """

    guess = last_proof + proof
    guess_hash = hashlib.sha256(guess).hexdigest()
    return guess_hash[:4] == '0000'


  @staticmethod
  def valid_chain(chain):
    """
    Determines if a given blockchain is valid.

    :param chain: <list> A blockchain
    :return: <bool> Whther the blockchain is valid.
    """

    last_block = chain[0]
    current_index = 1

    while current_index < len(chain):
      block = chain[current_index]
      print('{last_block} \n>>>\n {block}\n------\n'.format(
        last_block=last_block, block = block))

      # Check that the hash of the block is correct.
      if block.previous_hash != Node.hash(last_block):
        return False

      # Check that the Proof of Work is correct.
      if not Node.valid_proof(last_block.proof, block.proof):
        return False

      last_block = block
      current_index += 1
    return True


  def resolve_conflicts(self):
    """
    This is our Consensus Algorithm, it resolves conflicts by replacing our
    chain with the longest one in the network.

    :return: <bool> True if our chain was replaced, False if not.
    """
    new_chain = None

    # We've only looking for chains longer than ours
    max_length = len(self.chain)

    for node_id in self.neighbor_nodes:
      node = Node.get_by_id(node_id)
      if not node: continue

      # Check if the length is longer and the chain is valid
      if len(node.chain) > max_length and Node.valid_chain(node.chain):
        max_length = len(node.chain)
        new_chain = node.chain

    # Replace our chain if we discovered a new, valid chain longer than ours.
    if new_chain:
      self.chain = new_chain
      return True
    return False


def login_required(f):
  """A decorator that requires a currently logged in user."""
  @functools.wraps(f)
  def wrapper(*args, **kwargs):
    user = users.get_current_user()
    if user is None:
      login_url = users.create_login_url('/')
      return redirect(login_url)
    node_id = user.email()
    node = Node.get_by_id(node_id)
    if node is None:
      node = Node(id=node_id)
      node.new_block(previous_hash='1', proof=node_id.split('@')[0])
      node.put()
    return f(user, node, *args, **kwargs)
  return wrapper


@app.route('/')
@login_required
def home(user, node):
  message = request.args.get('message', None)
  status = request.args.get('status', None)
  ref = request.args.get('ref', None)
  return render_template(
      'node.tpl', node=node, message=message, status=status, ref=ref)


@app.route('/mine', methods=['POST'])
@login_required
def mine(user, node):
  last_proof = request.form['lastproof']
  proof = request.form['proof']
  if last_proof != node.chain[-1].proof:
    response = {
      'message': 'Last proof does not match.',
      'status': 'ng',
    }
  else:
    result = Node.valid_proof(last_proof=last_proof, proof=proof)
    if result:
      # We must receive a reward for finding the proof.
      # The sender is "0" to signify that this node has mined a new coin.
      node.new_transaction(
        sender='0',
        recipient=node.key.id(),
        amount=1,
      )

      # Forge the new Block by adding it to the chain
      block = node.new_block(proof)

      response = {
        'message': 'You mined 1 coin.',
        'status': 'ok',
      }
    else:
      response = {
      'message': 'Challenge failed.',
      'status': 'ng',
      }
  response['ref'] = 'mine'
  return redirect(
      '/?message={message}&status={status}&ref={ref}'.format(**response))


@app.route('/transaction', methods=['POST'])
@login_required
def transaction(user, node):
  amount = int(request.form['amount'])
  recipient = request.form['recipient']
  node.new_transaction(sender=node.key.id(), recipient=recipient, amount=amount)
  node.put()
  response = {
      'message': 'Sent {amount} coins to {recipient}'.format(
        amount=amount, recipient=recipient),
      'status': 'ok',
      'ref': 'trans',
  }
  return redirect(
      '/?message={message}&status={status}&ref={ref}'.format(**response))


@app.route('/neighbor', methods=['POST'])
@login_required
def neighbor(user, node):
  neighbor_node_id = request.form['node']
  node.neighbor_nodes.append(neighbor_node_id)
  node.put()
  response = {
      'message': 'Neighbor %s is added.' % (neighbor_node_id),
      'status': 'ok',
      'ref': 'neighbor',
  }
  return redirect(
      '/?message={message}&status={status}&ref={ref}'.format(**response))


@app.route('/consensus', methods=['POST'])
@login_required
def consensus(user, node):
  updated = node.resolve_conflicts()
  node.put()
  response = {
      'message': 'Your chain is updated.' if updated else 'No update.',
      'status': 'ok',
      'ref': 'consensus',
  }
  return redirect(
      '/?message={message}&status={status}&ref={ref}'.format(**response))


###
### Error handlers
###
@app.errorhandler(500)
def server_error(e):
  # Log the error and stacktrace.
  logging.exception('An error occurred during a request.')
  return 'An internal error occurred.', 500
# [END app]
