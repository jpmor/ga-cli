from ga.legis import Client, Chamber, get_committee, get_committees

from ga.cli.sessions import resolve_session


def cmd_committees(client: Client, args):
    session = resolve_session(client, args.session)
    if args.id is not None:
        c = get_committee(client, args.id, session.id)
        print(f"{c.chamber.name} Committee on {c.name}")
        if c.phone:
            print(f"Phone: {c.phone}")
        if c.description:
            print(f"\n{c.description}")
        print(f"\nMembers ({len(c.members)}):")
        for m in c.members:
            print(f"  {m.role:30s}  {m.district:5s}  {m.name}")
        if c.subcommittees:
            print("\nSubcommittees:")
            for s in c.subcommittees:
                print(f"  {s}")
    else:
        chamber = Chamber[args.chamber.title()] if args.chamber else None
        committees = get_committees(client, session.id, chamber)
        for c in committees:
            print(f"{c.id:4d}  {c.chamber.name:6s}  {c.name}")
