from models import *

def main():
    my_product = StandardProduct("rh","liron","prada",12.0,60.0)
    second_product = PerishableProduct("cmm502","ruth","prada",12.0,"12/07/2002",True)
    first_warehouse= Location("1","first_warehouse","warehouse","modiin")
    print(my_product)
    print(second_product)
    print(first_warehouse)


if __name__ == '__main__':
    main()



