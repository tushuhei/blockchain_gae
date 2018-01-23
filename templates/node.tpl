<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,minimum-scale=1.0">
<title>Blockchain Simulation</title>
</head>

<body>
<h1>Blockchain Simulation</h1>
<p>Hello, Node #{{node.key.id()}}.</p>
<p>Your have {{node.coins}} coins now.</p>
<p>Your have {{node.current_transactions|length}} transactions to go into the next mined block.</p>
<hr>
<section id="mine">
  <h2>Mine a coin</h2>
  Find a number x such that sha256 hash ('{{node.chain[-1].proof}}' + x) contains leading 4 zeros.
  <form method="post" action="/mine">
    <label>Your answer:
      <input type="text" name="proof">
    </label>
    <input type="hidden" name="lastproof" value="{{node.chain[-1].proof}}">
    <input type="submit">
  </form>
  {% if ref == "mine" %}
    <p class="{{status}}"><b>{{message}}</b></p>
  {% endif %}
</section>
<hr>
<section>
  <h2>Make a transaction</h2>
  <form method="post" action="/transaction">
    <div>
    <label>Number of coins to send:
      <input type="number" name="amount">
    </label>
    </div>
    <div>
    <label>Node ID of the recipient:
      <input type="text" name="recipient">
    </label>
    </div>
    <input type="submit">
  </form>
  {% if ref == "trans" %}
    <p class="{{status}}"><b>{{message}}</b></p>
  {% endif %}
</section>
<hr>
<section>
  <h2>Add a neighbor</h2>
  <form method="post" action="/neighbor">
    <input type="text" name="node">
    <input type="submit">
  </form>
  {% if ref == "neighbor" %}
    <p class="{{status}}"><b>{{message}}</b></p>
  {% endif %}
</section>
<hr>
<section>
  <h2>Make a consensus</h2>
  <form method="post" action="/consensus">
    <input type="submit" value="resolve conflicts">
  </form>
  {% if ref == "consensus" %}
    <p class="{{status}}"><b>{{message}}</b></p>
  {% endif %}
</section>
<style>
  .ok {
    color: #0f0;
  }
  .ng {
    color: #f00;
  }
</style>
</body>
</html>
