import hug

pay = hug.payment.channel("0x3b63b366a72e5742b2aaa13a5e86725ed06a68f3")

@hug.get("/pay", requires=pay("1 wei"))
def pay_world(payment: hug.directives.payment):
    return "You paid {0} for this.".format(payment)