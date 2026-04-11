# GA Legis

**https://jpmor.github.io/ga-cli/** - Browse the Official Code of Georgia, free.

## Why this exists

Citizens benefit when they can read their own laws. They benefit when they can see what the legislature is working on, track a bill, or look up what their representative has sponsored. None of that should require a commercial subscription.

Right now, Georgia doesn't host its own legal code. The General Assembly's website and the Secretary of State's site both point to LexisNexis. Your options there are a 186-volume physical set for $412, or clicking through 28,000 sections one at a time on a website where sections can't be linked to and the law is typically over a year out of date.

In 2013, a nonprofit posted the OCGA online for free. Georgia sued them. The case went to the Supreme Court, which [ruled 5-4 in 2020](https://www.supremecourt.gov/opinions/19pdf/18-1150_new_d18e.pdf) that the state doesn't own the copyright to its own laws, and Georgia still doesn't host them.

The LexisNexis site has aggressive CAPTCHAs, slow page loads, limited search, and sections that can't be linked to. It is designed not to be read easily. That's worth keeping in mind when considering who benefits from the current arrangement.

There's also a deeper problem: every bill that passes contains instructions for how the code should be updated. That reconciliation, turning enacted legislation into updated law, currently happens inside LexisNexis, with no public process and no audit trail. A private company, under contract, is effectively the final step in Georgia's lawmaking.

This project is a small attempt to improve on that. The web browser is a start. The longer-term goal is a version of the code maintained directly from the bills that pass, one commit per enacted law, publicly auditable.

## The code browser

**https://jpmor.github.io/ga-cli/**

All 53 titles of the OCGA, browsable and linkable, sourced from the state's own website and served as static files from this repository. No account required.

## The command-line tool

For querying legislative data in bulk: members, committees, bills back to 2001.

```
git clone https://github.com/jpmor/ga-cli
cd ga-cli
./ga-cli --help
```

Python 3.11+. No external dependencies.

## Contributing

Issues and pull requests welcome. If you work in or around the General Assembly and have thoughts on how this could be more useful, I'd especially like to hear from you.
